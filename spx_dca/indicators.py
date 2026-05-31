"""Monthly indicator engineering with explicit anti-lookahead alignment."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .config import AppConfig
from .data_sources import load_raw_or_fetch, to_monthly
from .utils import month_end_index, write_metadata

LOGGER = logging.getLogger(__name__)


def _lag_macro(s: pd.Series, months: int) -> pd.Series:
    """Apply a conservative publication lag to monthly macro data."""
    return s.shift(months) if months > 0 else s


def _status_bucket(value: float, thresholds: list[tuple[float, str]], default: str) -> str:
    if pd.isna(value):
        return "Missing"
    for threshold, label in thresholds:
        if value < threshold:
            return label
    return default


def build_monthly_panel(cfg: AppConfig) -> pd.DataFrame:
    """Build and persist the full monthly feature panel from raw public sources."""
    raw = load_raw_or_fetch(cfg)
    t = cfg.thresholds
    monthly: dict[str, pd.Series] = {}

    spx_daily = raw.get("sp500")
    if spx_daily is None or spx_daily.empty:
        raise RuntimeError("S&P 500 data unavailable from FRED and fallback")
    monthly["spx_close"] = to_monthly(spx_daily, "last")

    if "cape" in raw:
        monthly["cape"] = to_monthly(raw["cape"], "last")
    override = cfg.data.get("manual_overrides", {}).get("cape")
    if override is not None:
        idx = monthly["spx_close"].index
        cape = monthly.get("cape", pd.Series(index=idx, dtype=float)).reindex(idx)
        cape.iloc[-1] = float(override)
        monthly["cape"] = cape

    macro_names = ["baa", "aaa", "hy_oas", "unrate", "t10y3m", "t10y2y", "dgs10", "dgs3mo", "dgs2", "real_yield_10y"]
    for name in macro_names:
        if name in raw:
            monthly[name] = _lag_macro(to_monthly(raw[name], "last"), cfg.macro_lag_months)

    panel = pd.DataFrame(monthly).sort_index()
    panel = panel.loc[panel.index >= pd.Period(cfg.start_date, "M").to_timestamp("M")]
    panel.index.name = "month"

    # Price and trend.
    panel["spx_10m_ma"] = panel["spx_close"].rolling(10, min_periods=10).mean()
    panel["above_10m_ma"] = panel["spx_close"] > panel["spx_10m_ma"]
    panel["return_1m"] = panel["spx_close"].pct_change(1)
    panel["return_3m"] = panel["spx_close"].pct_change(3)
    panel["return_6m"] = panel["spx_close"].pct_change(6)
    panel["return_12m"] = panel["spx_close"].pct_change(12)
    panel["momentum_12m_positive"] = panel["return_12m"] > 0
    panel["rolling_high"] = panel["spx_close"].cummax()
    panel["drawdown"] = panel["spx_close"] / panel["rolling_high"] - 1

    # Valuation.
    if "cape" not in panel:
        panel["cape"] = np.nan
    panel["cape_bucket"] = panel["cape"].apply(
        lambda x: _status_bucket(
            x,
            [(t["cape_green_lt"], "Green"), (t["cape_yellow_lt"], "Yellow"), (t["cape_orange_lt"], "Orange"), (t["cape_bubble_gte"], "Orange-Extreme")],
            "Bubble",
        )
    )

    # Credit.
    panel["baa_aaa_spread"] = panel.get("baa") - panel.get("aaa") if {"baa", "aaa"}.issubset(panel.columns) else np.nan
    panel["baa_aaa_6m_change"] = panel["baa_aaa_spread"].diff(6)
    panel["credit_status"] = panel["baa_aaa_spread"].apply(
        lambda x: _status_bucket(
            x,
            [(t["baa_calm_lt"], "Calm"), (t["baa_watch_lt"], "Watch"), (t["baa_stress_lt"], "Stress")],
            "Serious stress",
        )
    )
    if "hy_oas" in panel:
        panel["hy_oas_6m_change"] = panel["hy_oas"].diff(6)
    else:
        panel["hy_oas"] = np.nan
        panel["hy_oas_6m_change"] = np.nan

    # Labor.
    if "unrate" in panel:
        panel["unrate_3m_avg"] = panel["unrate"].rolling(3, min_periods=3).mean()
        panel["unrate_12m_min_3m_avg"] = panel["unrate_3m_avg"].rolling(12, min_periods=1).min()
        panel["sahm_gap"] = panel["unrate_3m_avg"] - panel["unrate_12m_min_3m_avg"]
    else:
        panel["unrate_3m_avg"] = panel["unrate_12m_min_3m_avg"] = panel["sahm_gap"] = np.nan
    panel["labor_status"] = panel["sahm_gap"].apply(
        lambda x: _status_bucket(x, [(t["sahm_watch"], "Calm"), (t["sahm_stress"], "Watch")], "Recession warning")
    )

    # Yield curve fallback hierarchy.
    if "t10y3m" in panel and panel["t10y3m"].notna().any():
        panel["yc_10y3m"] = panel["t10y3m"]
    elif {"dgs10", "dgs3mo"}.issubset(panel.columns):
        panel["yc_10y3m"] = panel["dgs10"] - panel["dgs3mo"]
    else:
        panel["yc_10y3m"] = np.nan
    if "t10y2y" in panel and panel["t10y2y"].notna().any():
        panel["yc_10y2y"] = panel["t10y2y"]
    elif {"dgs10", "dgs2"}.issubset(panel.columns):
        panel["yc_10y2y"] = panel["dgs10"] - panel["dgs2"]
    else:
        panel["yc_10y2y"] = np.nan
    panel["yield_curve"] = panel["yc_10y3m"].combine_first(panel["yc_10y2y"])
    panel["curve_inverted"] = panel["yield_curve"] < 0
    was_inverted = panel["curve_inverted"].rolling(12, min_periods=1).max().shift(1).fillna(False).astype(bool)
    panel["curve_resteepening_after_inversion"] = was_inverted & ((panel["yield_curve"] > 0) | (panel["yield_curve"].diff(3) >= 0.75))

    # Real yield.
    if "real_yield_10y" not in panel:
        panel["real_yield_10y"] = np.nan
    def real_status(x: float) -> str:
        if pd.isna(x):
            return "Missing"
        if x < t["real_yield_supportive_lt"]:
            return "Supportive"
        if x < t["real_yield_neutral_lt"]:
            return "Neutral"
        if x < t["real_yield_tight_lt"]:
            return "Tight"
        return "Very tight"
    panel["real_yield_status"] = panel["real_yield_10y"].apply(real_status)

    panel.index = month_end_index(panel.index)
    out = cfg.processed_dir / "monthly_panel.csv"
    panel.to_csv(out)
    write_metadata(out, {"source": "processed public monthly panel", "macro_lag_months": cfg.macro_lag_months})
    LOGGER.info("Wrote %s rows to %s", len(panel), out)
    return panel


def load_monthly_panel(cfg: AppConfig) -> pd.DataFrame:
    path = cfg.processed_dir / "monthly_panel.csv"
    if not path.exists():
        return build_monthly_panel(cfg)
    return pd.read_csv(path, parse_dates=["month"], index_col="month")
