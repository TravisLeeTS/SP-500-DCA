import pandas as pd

from spx_dca.config import load_config
from spx_dca.regime import classify_row


def base_row(**overrides):
    row = {
        "cape": 20.0,
        "spx_close": 100.0,
        "spx_10m_ma": 90.0,
        "above_10m_ma": True,
        "return_12m": 0.12,
        "drawdown": 0.0,
        "baa_aaa_spread": 0.8,
        "baa_aaa_6m_change": 0.0,
        "hy_oas": pd.NA,
        "sahm_gap": 0.1,
        "yield_curve": 1.0,
        "curve_inverted": False,
        "curve_resteepening_after_inversion": False,
        "real_yield_10y": pd.NA,
    }
    row.update(overrides)
    return pd.Series(row)


def cfg():
    return load_config("configs/config.yaml")


def test_valuation_alone_cannot_trigger_red():
    decision = classify_row(base_row(cape=42.0), cfg())
    assert decision.regime == "Orange-A"


def test_trend_break_plus_credit_stress_can_trigger_red():
    decision = classify_row(
        base_row(cape=32.0, above_10m_ma=False, return_12m=-0.05, drawdown=-0.12, baa_aaa_spread=1.8), cfg()
    )
    assert decision.regime == "Red"


def test_deep_drawdown_overrides_red():
    decision = classify_row(
        base_row(cape=32.0, above_10m_ma=False, return_12m=-0.20, drawdown=-0.22, baa_aaa_spread=2.2), cfg()
    )
    assert decision.regime == "Accumulation-2"
    assert "stages" in decision.caution


def test_calm_cheap_market_is_green():
    decision = classify_row(base_row(cape=20.0), cfg())
    assert decision.regime == "Green"


def test_expensive_but_healthy_market_is_orange_a():
    decision = classify_row(base_row(cape=38.0), cfg())
    assert decision.regime == "Orange-A"


def test_expensive_and_weakening_market_is_orange_b():
    decision = classify_row(base_row(cape=36.0, drawdown=-0.08, above_10m_ma=False), cfg())
    assert decision.regime == "Orange-B"
