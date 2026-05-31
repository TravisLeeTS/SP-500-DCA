"""Deterministic monthly regime classification rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .config import AppConfig
from .utils import num, pct

REGIME_ORDER = ["Green", "Yellow", "Orange-A", "Orange-B", "Red", "Accumulation-1", "Accumulation-2", "Accumulation-3"]


@dataclass(frozen=True)
class RegimeDecision:
    regime: str
    dca_amount_aed: int
    confidence: str
    explanation: str
    caution: str = ""


def _b(row: pd.Series | dict[str, Any], key: str, default: bool = False) -> bool:
    value = row.get(key, default)
    if pd.isna(value):
        return default
    return bool(value)


def _f(row: pd.Series | dict[str, Any], key: str, default: float = float("nan")) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_rule_flags(row: pd.Series | dict[str, Any], cfg: AppConfig) -> dict[str, bool | int]:
    """Compute transparent rule flags from one monthly row."""
    t = cfg.thresholds
    cape = _f(row, "cape")
    drawdown = _f(row, "drawdown", 0.0)
    ret12 = _f(row, "return_12m")
    spread = _f(row, "baa_aaa_spread")
    spread_chg = _f(row, "baa_aaa_6m_change")
    hy = _f(row, "hy_oas")
    sahm = _f(row, "sahm_gap")
    real_yield = _f(row, "real_yield_10y")

    trend_break = not _b(row, "above_10m_ma")
    negative_momentum = pd.notna(ret12) and ret12 < 0
    trend_damage_count = int(trend_break) + int(negative_momentum) + int(pd.notna(drawdown) and drawdown <= t["drawdown_warning"])

    credit_stress = (pd.notna(spread) and spread >= t["baa_watch_lt"]) or (pd.notna(spread_chg) and spread_chg >= t["baa_fast_widening"])
    serious_credit_stress = (pd.notna(spread) and spread >= t["baa_stress_lt"]) or (pd.notna(hy) and hy >= t["hy_serious"])
    labor_stress = pd.notna(sahm) and sahm >= t["sahm_stress"]
    labor_watch = pd.notna(sahm) and sahm >= t["sahm_watch"]
    curve_warning = _b(row, "curve_inverted") or _b(row, "curve_resteepening_after_inversion")
    macro_stress_count = int(credit_stress) + int(labor_stress) + int(curve_warning)

    valuation_high = pd.notna(cape) and cape >= t["cape_yellow_lt"]
    valuation_extreme = pd.notna(cape) and cape >= t["cape_extreme_gte"]
    valuation_bubble = pd.notna(cape) and cape >= t["cape_bubble_gte"]
    rates_tight = pd.notna(real_yield) and real_yield >= t["real_yield_neutral_lt"]
    rates_very_tight = pd.notna(real_yield) and real_yield >= t["real_yield_tight_lt"]
    backdrop_risk = valuation_high or rates_tight or curve_warning
    trend_healthy = _b(row, "above_10m_ma") and (pd.isna(ret12) or ret12 > 0)

    return {
        "trend_break": trend_break,
        "negative_momentum": negative_momentum,
        "trend_damage_count": trend_damage_count,
        "credit_stress": credit_stress,
        "serious_credit_stress": serious_credit_stress,
        "labor_stress": labor_stress,
        "labor_watch": labor_watch,
        "curve_warning": curve_warning,
        "macro_stress_count": macro_stress_count,
        "valuation_high": valuation_high,
        "valuation_extreme": valuation_extreme,
        "valuation_bubble": valuation_bubble,
        "rates_tight": rates_tight,
        "rates_very_tight": rates_very_tight,
        "backdrop_risk": backdrop_risk,
        "trend_healthy": trend_healthy,
    }


def confidence_for_row(row: pd.Series | dict[str, Any]) -> str:
    """Score confidence from available core modules."""
    modules = {
        "price/trend": ["spx_close", "spx_10m_ma", "return_12m", "drawdown"],
        "valuation": ["cape"],
        "credit": ["baa_aaa_spread"],
        "labor": ["sahm_gap"],
        "curve": ["yield_curve"],
    }
    available = 0
    for cols in modules.values():
        if any(pd.notna(row.get(c, float("nan"))) for c in cols):
            available += 1
    if available >= 5:
        return "High"
    if available >= 3:
        return "Medium"
    return "Low"


def classify_row(row: pd.Series | dict[str, Any], cfg: AppConfig) -> RegimeDecision:
    """Classify one month into the DCA guide regime without using future data."""
    t = cfg.thresholds
    flags = compute_rule_flags(row, cfg)
    dd = _f(row, "drawdown", 0.0)
    cape = _f(row, "cape")
    spread = _f(row, "baa_aaa_spread")
    sahm = _f(row, "sahm_gap")
    ret12 = _f(row, "return_12m")

    caution = ""
    if pd.notna(dd) and dd <= t["accumulation_3_dd"]:
        regime = "Accumulation-3"
    elif pd.notna(dd) and dd <= t["accumulation_2_dd"]:
        regime = "Accumulation-2"
    elif pd.notna(dd) and dd <= t["accumulation_1_dd"]:
        regime = "Accumulation-1"
    else:
        regime = ""
    if regime:
        if flags["serious_credit_stress"] and flags["credit_stress"]:
            caution = "Credit stress is serious; deploy dry powder in stages with caution."
        explanation = (
            f"{regime}: S&P 500 drawdown is {pct(dd)}, so the guide shifts from peak-risk avoidance "
            "to staged accumulation; bad news does not cancel the drawdown override."
        )
        return RegimeDecision(regime, cfg.dca_default(regime), confidence_for_row(row), explanation, caution)

    red = (flags["backdrop_risk"] and flags["trend_damage_count"] >= 2 and flags["macro_stress_count"] >= 1) or (
        flags["backdrop_risk"] and flags["trend_damage_count"] >= 1 and flags["macro_stress_count"] >= 2
    )
    if red:
        regime = "Red"
        explanation = (
            "Red: backdrop risk is present and trend damage is confirmed with macro/credit/labor stress. "
            "Use symbolic DCA only; valuation alone did not trigger this signal."
        )
    elif (
        (flags["valuation_extreme"] and flags["trend_damage_count"] >= 1)
        or (flags["valuation_extreme"] and (flags["credit_stress"] or flags["labor_watch"]))
        or (flags["valuation_high"] and flags["rates_very_tight"] and flags["trend_damage_count"] >= 1)
        or (pd.notna(dd) and t["accumulation_1_dd"] < dd <= t["orange_b_drawdown"])
    ):
        regime = "Orange-B"
        explanation = (
            f"Orange-B: market is expensive or weakening (CAPE {num(cape, 1)}, drawdown {pct(dd)}), "
            "but Red is not fully confirmed. Keep DCA reduced rather than stopped."
        )
    elif flags["valuation_extreme"] and flags["trend_healthy"] and not flags["credit_stress"] and not flags["labor_watch"]:
        regime = "Orange-A"
        explanation = (
            f"Orange-A: CAPE is extreme at {num(cape, 1)}, but price is above the 10-month MA, "
            "12-month momentum is positive, and credit/labor stress is not confirmed."
        )
    elif flags["valuation_high"] and not flags["valuation_extreme"] and flags["trend_healthy"] and not flags["credit_stress"] and not flags["labor_watch"]:
        regime = "Yellow"
        explanation = (
            f"Yellow: valuation is elevated (CAPE {num(cape, 1)}) while trend and macro conditions remain calm."
        )
    elif (not flags["valuation_high"]) and flags["trend_healthy"] and not flags["credit_stress"] and not flags["labor_watch"]:
        regime = "Green"
        explanation = (
            f"Green: valuation is not high, trend is healthy, 12-month return is {pct(ret12)}, "
            f"Baa-Aaa spread is {num(spread)} pp, and Sahm gap is {num(sahm)}."
        )
    else:
        regime = "Yellow"
        explanation = "Yellow: mixed or incomplete signals justify normal-to-reduced DCA while waiting for confirmation."

    return RegimeDecision(regime, cfg.dca_default(regime), confidence_for_row(row), explanation, caution)


def classify_panel(panel: pd.DataFrame, cfg: AppConfig) -> pd.DataFrame:
    """Classify every month and persist monthly regimes."""
    records = []
    for month, row in panel.iterrows():
        decision = classify_row(row, cfg)
        records.append(
            {
                "month": month,
                "regime": decision.regime,
                "dca_amount_aed": decision.dca_amount_aed,
                "confidence": decision.confidence,
                "explanation": decision.explanation,
                "caution": decision.caution,
            }
        )
    regimes = pd.DataFrame(records).set_index("month")
    combined = panel.join(regimes)
    out = cfg.processed_dir / "monthly_regimes.csv"
    combined.to_csv(out)
    return combined


def load_or_classify(panel: pd.DataFrame, cfg: AppConfig) -> pd.DataFrame:
    path = cfg.processed_dir / "monthly_regimes.csv"
    if path.exists():
        return pd.read_csv(path, parse_dates=["month"], index_col="month")
    return classify_panel(panel, cfg)
