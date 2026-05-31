"""Forward-outcome evaluation for the regime guide."""
from __future__ import annotations

import pandas as pd

from .config import AppConfig
from .regime import classify_panel

EPISODES = [
    ("1970 bear market", "1970-01", "1970-12"),
    ("1973-1974 oil shock and inflation bear", "1973-01", "1974-12"),
    ("1980 recession", "1980-01", "1980-12"),
    ("1981-1982 Volcker tightening bear", "1981-01", "1982-12"),
    ("1987 crash", "1987-08", "1987-12"),
    ("1990 recession", "1990-07", "1990-12"),
    ("1998 LTCM crisis", "1998-07", "1998-12"),
    ("2000-2002 dot-com bear", "2000-01", "2002-12"),
    ("2007-2009 GFC", "2007-10", "2009-03"),
    ("2011 euro crisis", "2011-07", "2011-12"),
    ("2015-2016 China/oil/industrial slowdown", "2015-05", "2016-03"),
    ("2018 Q4 Fed tightening correction", "2018-09", "2018-12"),
    ("2020 COVID crash", "2020-02", "2020-04"),
    ("2021-2022 inflation/rate bear", "2021-11", "2022-12"),
    ("2023-2026 AI-led expensive bull market", "2023-01", "2026-12"),
]


def add_forward_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Add forward returns/drawdowns for evaluation only, never signals."""
    out = df.copy()
    close = out["spx_close"]
    for horizon in [6, 12, 24, 36]:
        out[f"forward_{horizon}m_return"] = close.shift(-horizon) / close - 1
        max_dd = []
        for i in range(len(close)):
            future = close.iloc[i + 1 : i + horizon + 1]
            if future.empty or pd.isna(close.iloc[i]):
                max_dd.append(pd.NA)
                continue
            running_high = pd.concat([pd.Series([close.iloc[i]]), future.reset_index(drop=True)]).cummax().iloc[1:]
            dd = future.reset_index(drop=True) / running_high - 1
            max_dd.append(dd.min())
        out[f"max_dd_next_{horizon}m"] = max_dd
        if horizon in [12, 24, 36]:
            out[f"bad_{horizon}m"] = (out[f"forward_{horizon}m_return"] < 0) | (out[f"max_dd_next_{horizon}m"] <= -0.20)
    return out


def summarize_by_regime(bt: pd.DataFrame) -> pd.DataFrame:
    """Aggregate backtest outcomes by regime."""
    rows = []
    for regime, group in bt.groupby("regime", dropna=False):
        row = {"regime": regime, "months": len(group), "avg_dca_aed": group["dca_amount_aed"].mean()}
        for horizon in [6, 12, 24, 36]:
            row[f"avg_fwd_{horizon}m"] = group[f"forward_{horizon}m_return"].mean()
            row[f"median_fwd_{horizon}m"] = group[f"forward_{horizon}m_return"].median()
            row[f"avg_max_dd_{horizon}m"] = group[f"max_dd_next_{horizon}m"].mean()
        for horizon in [12, 24, 36]:
            row[f"bad_{horizon}m_rate"] = group[f"bad_{horizon}m"].mean()
        rows.append(row)
    return pd.DataFrame(rows).sort_values("regime")


def precision_metrics(bt: pd.DataFrame) -> dict[str, float]:
    """Compute simple precision and false-alarm metrics for Red and Orange-B+Red."""
    metrics: dict[str, float] = {}
    red = bt["regime"] == "Red"
    orb_red = bt["regime"].isin(["Orange-B", "Red"])
    for horizon in [12, 24, 36]:
        bad = bt[f"bad_{horizon}m"].fillna(False)
        metrics[f"red_precision_bad_{horizon}m"] = float((bad & red).sum() / red.sum()) if red.sum() else float("nan")
        metrics[f"orange_b_red_precision_bad_{horizon}m"] = float((bad & orb_red).sum() / orb_red.sum()) if orb_red.sum() else float("nan")
    metrics["false_red_months_12m"] = int((red & ~bt["bad_12m"].fillna(False)).sum())
    bear = bt["drawdown"] <= -0.20
    metrics["missed_bear_months_not_red_or_accumulation"] = int((bear & ~bt["regime"].isin(["Red", "Accumulation-1", "Accumulation-2", "Accumulation-3"])).sum())
    metrics["always_dca_avg_monthly_aed"] = float(bt["dca_amount_aed"].mean())
    return metrics


def episode_validation(bt: pd.DataFrame) -> pd.DataFrame:
    """Create a human-readable validation table for named market episodes."""
    rows = []
    for name, start, end in EPISODES:
        start_ts = pd.Period(start, "M").to_timestamp("M")
        end_ts = pd.Period(end, "M").to_timestamp("M")
        window = bt.loc[(bt.index >= start_ts) & (bt.index <= end_ts)]
        if window.empty:
            continue
        before = bt.loc[bt.index < start_ts].tail(3)
        accum = window[window["regime"].astype(str).str.startswith("Accumulation")]
        red = window[window["regime"] == "Red"]
        rows.append(
            {
                "episode": name,
                "period": f"{start} to {end}",
                "regime_before": ", ".join(before["regime"].astype(str).tail(3)) if not before.empty else "n/a",
                "regime_during": ", ".join(window["regime"].astype(str).drop_duplicates().tolist()),
                "first_red": red.index.min().strftime("%Y-%m") if not red.empty else "none",
                "first_accumulation": accum.index.min().strftime("%Y-%m") if not accum.empty else "none",
                "max_episode_drawdown": window["drawdown"].min(),
                "sensible_behavior": "Yes - accumulation after drawdown" if not accum.empty else "Shock/limited warning or no deep drawdown",
            }
        )
    return pd.DataFrame(rows)


def run_backtest(panel: pd.DataFrame, cfg: AppConfig, start: str = "1970-01") -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], pd.DataFrame]:
    """Classify regimes and evaluate forward outcomes from start onward."""
    classified = classify_panel(panel, cfg)
    bt = add_forward_outcomes(classified)
    bt = bt.loc[bt.index >= pd.Period(start, "M").to_timestamp("M")]
    summary = summarize_by_regime(bt)
    metrics = precision_metrics(bt)
    episodes = episode_validation(bt)
    bt.to_csv(cfg.processed_dir / "backtest_monthly.csv")
    summary.to_csv(cfg.processed_dir / "backtest_summary_by_regime.csv", index=False)
    episodes.to_csv(cfg.processed_dir / "episode_validation.csv", index=False)
    return bt, summary, metrics, episodes
