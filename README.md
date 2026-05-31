# S&P 500 Monthly DCA Regime Checker

A production-quality, transparent Python guide for sizing a monthly S&P 500 DCA contribution. The project is intentionally a **monthly DCA throttle**, not a trading system and not a market-top prediction model.

## Core Principles

- This is not financial advice.
- This is not a market-top prediction model.
- This is a monthly DCA throttle.
- It should be run once per month after month-end close.
- It should not be used for daily trading.
- It should not be used to sell everything.
- Valuation alone slows DCA but does not stop investing.
- Red requires trend damage plus macro/credit/labor confirmation.
- Deep drawdowns switch the model from peak avoidance to staged accumulation.
- The model is designed to reduce emotional decisions, not maximize short-term returns.

## What It Does

The system fetches public historical data, builds a month-end feature panel from 1970 onward, classifies each month into a deterministic regime, and generates DCA recommendations in AED.

Regimes:

- Green
- Yellow
- Orange-A
- Orange-B
- Red
- Accumulation-1
- Accumulation-2
- Accumulation-3

The guide follows this philosophy:

> Valuation slows me down. Trend + credit/labor stress pauses me. Deep drawdowns make me buy more, not less.

## Data Sources

Core public data sources:

- FRED `SP500` daily S&P 500 close, resampled to month-end; Yahoo `^GSPC` fallback is supported.
- Robert Shiller/Yale monthly CAPE/PE10.
- FRED `BAA` and `AAA`, used as a long-history credit stress proxy.
- FRED `BAMLH0A0HYM2` high-yield OAS where available.
- FRED `UNRATE` for Sahm-style labor stress.
- FRED `T10Y3M`, `T10Y2Y`, and optional direct Treasury yields for yield-curve signals.
- FRED `DFII10` for 10-year TIPS real yield from 2003 onward. Missing pre-2003 real yield is not penalized.

Raw downloads are cached in `data/raw/`, and processed outputs are written to `data/processed/`.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11+ is required.

## CLI Usage

```bash
python -m spx_dca fetch-data
python -m spx_dca build-panel
python -m spx_dca run-current
python -m spx_dca run-recent --months 12
python -m spx_dca backtest --start 1970-01
python -m spx_dca make-report
python -m spx_dca run-all
```

## Configuration

All personal DCA amounts and rule thresholds live in `configs/config.yaml`. The default normal monthly S&P 500 DCA budget is AED 5,000, with a configurable normal range of AED 4,000 to AED 6,000.

Macro data uses a conservative one-month lag by default to reduce lookahead risk. You can adjust this through `macro_lag_months`.

If the latest CAPE is unavailable, set `manual_overrides.cape` and document the source in `manual_overrides.cape_source_note`. Manual values are explicit rather than silently fabricated.

## Rule Summary

### Drawdown Override

- Drawdown <= -15%: Accumulation-1
- Drawdown <= -20%: Accumulation-2
- Drawdown <= -30%: Accumulation-3

Credit stress can add a caution note, but it does not cancel accumulation. Deep drawdowns are treated as staged buying opportunities.

### Red Requires Confirmation

Red can occur only when there is backdrop risk plus confirmed trend damage and macro/credit/labor stress. High CAPE alone cannot trigger Red.

### Expensive Bull Markets

High or extreme valuation with healthy trend, positive momentum, calm credit, and calm labor becomes Yellow or Orange-A, not Red.

## Outputs

Generated files include:

- `data/processed/monthly_panel.csv`: full feature dataset.
- `data/processed/monthly_regimes.csv`: month, regime, DCA amount, features, and explanation.
- `reports/current_month_report.md`: current monthly recommendation.
- `reports/recent_12_months.md`: recent month-by-month guide.
- `reports/backtest_1970_latest.md`: descriptive backtest and episode validation.

## Backtest Notes

The backtest evaluates forward 6-, 12-, 24-, and 36-month price returns and forward max drawdowns. These forward outcomes are evaluation labels only and are never used to construct the month-end signal.

The framework is deliberately not curve-fit. Thresholds are stable and economically motivated, and the system admits that sudden shocks such as 1987 or COVID may not be predicted before the event. In those cases, sensible behavior means switching to accumulation after drawdowns rather than pretending to forecast the crash.

## Tests

```bash
pytest
```

Tests cover core regime edge cases, no-lookahead behavior, month-end resampling, and backtest output columns.
