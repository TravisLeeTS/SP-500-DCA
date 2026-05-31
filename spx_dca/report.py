"""Markdown report generation."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .backtest import run_backtest
from .config import AppConfig
from .indicators import load_monthly_panel
from .regime import classify_panel
from .utils import num, pct

SIGNAL_COLS = [
    "cape", "spx_close", "spx_10m_ma", "return_12m", "drawdown", "baa_aaa_spread", "hy_oas", "sahm_gap", "yield_curve", "real_yield_10y",
]


def _format_signal_table(row: pd.Series) -> str:
    labels = {
        "cape": "CAPE", "spx_close": "S&P close", "spx_10m_ma": "10M MA", "return_12m": "12M return", "drawdown": "Drawdown",
        "baa_aaa_spread": "Baa-Aaa spread", "hy_oas": "HY OAS", "sahm_gap": "Sahm gap", "yield_curve": "Yield curve", "real_yield_10y": "Real yield",
    }
    lines = ["| Signal | Value |", "|---|---:|"]
    for col in SIGNAL_COLS:
        val = row.get(col)
        if col in {"return_12m", "drawdown"}:
            fval = pct(val)
        else:
            fval = num(val, 2)
        lines.append(f"| {labels[col]} | {fval} |")
    return "\n".join(lines)


def next_triggers(row: pd.Series) -> tuple[str, str]:
    downgrade = "S&P closes below the 10-month MA with Baa-Aaa spread above 1.5 pp, Sahm gap above 0.5, or renewed curve stress."
    upgrade = "CAPE falls below 30, trend/momentum improve, credit/labor stress fades, or a 15%+ drawdown moves the guide into accumulation."
    if str(row.get("regime", "")).startswith("Accumulation"):
        downgrade = "Credit stress keeps worsening; continue staged buying rather than lump-summing."
        upgrade = "Market recovers above the accumulation drawdown zone or stress normalizes."
    return downgrade, upgrade


def write_current_report(regimes: pd.DataFrame, cfg: AppConfig) -> Path:
    row = regimes.dropna(subset=["regime"]).iloc[-1]
    month = row.name.strftime("%Y-%m")
    lo, hi = cfg.dca_range(row["regime"])
    downgrade, upgrade = next_triggers(row)
    text = f"""# Current Monthly S&P 500 DCA Regime Report

**Month:** {month}  
**Current regime:** {row['regime']}  
**Recommended S&P 500 DCA:** AED {int(row['dca_amount_aed']):,}  
**Configured range:** AED {lo:,} to AED {hi:,}  
**Confidence:** {row['confidence']}

## Explanation

{row['explanation']}

{('**Safety note:** ' + row['caution']) if isinstance(row.get('caution'), str) and row.get('caution') else ''}

## Signal Table

{_format_signal_table(row)}

## What would change the guide next month?

- **Next downgrade trigger:** {downgrade}
- **Next upgrade trigger:** {upgrade}

## Final monthly decision

Regime: {row['regime']}  
Recommended S&P 500 DCA: AED {int(row['dca_amount_aed']):,}  
Action: {'Continue staged accumulation while preserving emergency fund and dry powder.' if str(row['regime']).startswith('Accumulation') else 'Follow the reduced/normal DCA amount. Avoid leverage. Keep dry powder.'}  
Main reason: {row['explanation']}  
Next downgrade trigger: {downgrade}  
Next upgrade trigger: {upgrade}
"""
    path = cfg.reports_dir / "current_month_report.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_recent_report(regimes: pd.DataFrame, cfg: AppConfig, months: int = 12) -> Path:
    recent = regimes.dropna(subset=["regime"]).tail(months)
    lines = ["# Recent Monthly S&P 500 DCA Guide", "", "| Month | Regime | DCA AED | Confidence | Explanation |", "|---|---|---:|---|---|"]
    for month, row in recent.iterrows():
        lines.append(f"| {month.strftime('%Y-%m')} | {row['regime']} | {int(row['dca_amount_aed']):,} | {row['confidence']} | {row['explanation']} |")
    lines += ["", "## Conservatism Review", "", "This guide is intentionally conservative when valuation is high, but it is not designed to fully stop investing unless Red is confirmed. Accumulation regimes intentionally become more aggressive after deep drawdowns."]
    path = cfg.reports_dir / "recent_12_months.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_backtest_report(panel: pd.DataFrame, cfg: AppConfig, start: str = "1970-01") -> Path:
    bt, summary, metrics, episodes = run_backtest(panel, cfg, start=start)
    lines = ["# Backtest Report: 1970 to Latest", "", "This report evaluates forward outcomes only after each monthly regime has been generated. Forward returns are not used in signal construction.", ""]
    lines += ["## Regime Distribution and Forward Outcomes", "", summary.to_markdown(index=False, floatfmt=".3f"), ""]
    lines += ["## Precision / False Alarm Metrics", "", "| Metric | Value |", "|---|---:|"]
    for k, v in metrics.items():
        lines.append(f"| {k} | {v:.3f} |" if isinstance(v, float) else f"| {k} | {v} |")
    lines += ["", "## Episode Validation", "", episodes.to_markdown(index=False, floatfmt=".3f"), ""]
    lines += [
        "## Lessons and Limitations", "",
        "- Valuation alone slows DCA but does not stop investing or trigger Red.",
        "- Red requires trend damage plus macro/credit/labor confirmation.",
        "- Sudden shocks such as 1987 and COVID may not be predicted in advance; the guide should switch to accumulation after drawdowns.",
        "- Backtest statistics are descriptive and are not optimized trading rules.",
        "- This is not financial advice and should be run once per month after month-end close.",
    ]
    path = cfg.reports_dir / "backtest_1970_latest.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def make_all_reports(cfg: AppConfig, recent_months: int = 12, start: str = "1970-01") -> list[Path]:
    panel = load_monthly_panel(cfg)
    regimes = classify_panel(panel, cfg)
    return [
        write_current_report(regimes, cfg),
        write_recent_report(regimes, cfg, months=recent_months),
        write_backtest_report(panel, cfg, start=start),
    ]
