# Current Monthly S&P 500 DCA Regime Report

**Run date:** 2026-05-31  
**Effective market data date:** 2026-05-29 close, because 2026-05-31 is a Sunday and U.S. markets are closed.  
**Current regime:** Orange-A  
**Recommended S&P 500 DCA:** AED 2,750  
**Configured range:** AED 2,000 to AED 3,500  
**Confidence:** Medium

## Explanation

Orange-A: CAPE is in bubble/extreme territory, but the S&P 500 is above its 10-month moving average, 12-month momentum is positive, credit spreads are calm, labor stress is not confirmed, and the market is at/near a new high rather than in a drawdown. Continue reduced DCA and avoid lump sum.

## Signal Table

| Signal | Latest value used | Status | Notes |
|---|---:|---|---|
| CAPE / Shiller PE | 42.66 | Bubble | Multpl reported Shiller PE 42.66 at 4:00 PM EDT, Fri 2026-05-29. |
| S&P 500 close | 7,580.06 | Healthy trend | AP reported the S&P 500 closed at 7,580.06 on Fri 2026-05-29. |
| 10-month MA | ~6,800-6,900 | Above MA | Estimated from recent monthly S&P 500 closes; exact project calculation could not be run because dependencies are unavailable in this environment. |
| 12-month price return | ~+30% | Positive momentum | Approximate versus May 2025 S&P 500 level near 5,800-5,900. |
| Drawdown from rolling high | ~0% | No accumulation override | S&P 500 closed at a fresh/recent all-time high. |
| Baa-Aaa spread | ~0.61 pp | Calm | April 2026 monthly Baa around 6.03% and Aaa 5.42%; with the project default 1-month macro lag, this is the value bucket used for May guidance. |
| HY OAS | 2.76% | Calm | HY spread was far below the 4.5% warning and 5.5% serious thresholds. |
| Sahm/labor stress | Not confirmed | Calm/watch below Red threshold | April unemployment was 4.3% and unchanged from March; no confirmed Sahm-style recession warning was available from the latest public report. |
| Yield curve | Positive, ~+0.6 to +0.9 pp | Not inverted | 10Y-3M spread was positive in April/May 2026. |
| 10-year real yield | ~2.17%-2.18% | Very tight | Real rates are tight, which supports a reduced-DCA stance but does not trigger Red without trend/macro confirmation. |

## Rule Check

| Rule module | Result |
|---|---|
| Drawdown override | Not active: drawdown is nowhere near -15%, -20%, or -30%. |
| Valuation | Extreme/bubble: slows DCA. |
| Trend | Healthy: close is above 10-month MA and 12-month momentum is positive. |
| Credit | Calm: Baa-Aaa and HY spreads are below stress thresholds. |
| Labor | No confirmed stress: unemployment is stable at 4.3%. |
| Rates | Very tight real yield: cautionary, but not enough for Red by itself. |
| Red test | Failed: no trend damage and no macro/credit/labor confirmation. |

## What would change the guide next month?

- **Next downgrade trigger:** S&P 500 closes below its 10-month MA, 12-month momentum weakens materially, and Baa-Aaa spread widens above 1.5 pp or Sahm gap reaches 0.5.
- **Next upgrade trigger:** CAPE falls below 30, credit/rate pressure eases while trend remains healthy, or the S&P 500 corrects 15%+ into the Accumulation-1 zone.

## Final monthly decision

Regime: Orange-A  
Recommended S&P 500 DCA: AED 2,750  
Action: Continue reduced DCA. Do not lump sum. Keep dry powder and avoid leverage.  
Main reason: Valuation is extreme, but trend remains healthy and credit/labor stress is not confirmed.  
Next downgrade trigger: S&P closes below the 10-month MA and Baa-Aaa spread widens above 1.5 pp, or labor stress confirms via Sahm-style deterioration.  
Next upgrade trigger: CAPE falls below 30 or the market corrects 15%+ into the accumulation zone.

## Run limitation

The repository CLI could not be executed end-to-end in this environment because required Python dependencies such as `pandas`, `numpy`, and `requests` are not installed, and package installation is blocked by a 403 response from the package index. This report is therefore a manual current-month run using public web-observed values, not a full regenerated `monthly_panel.csv` backtest run.

## Public sources used for this manual run

- AP market wrap for the 2026-05-29 S&P 500 close.
- Multpl current market data for Shiller PE/CAPE on 2026-05-29.
- YCharts/Equibles/Macrotrends public snippets for April/May 2026 Aaa, Baa, and high-yield spread context.
- BLS Employment Situation for April 2026 unemployment.
- Public yield-curve and real-yield snippets for April/May 2026 Treasury and TIPS context.
