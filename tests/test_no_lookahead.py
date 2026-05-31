import pandas as pd

from spx_dca.config import load_config
from spx_dca.regime import classify_panel


def make_panel(last_cape):
    idx = pd.date_range("2020-01-31", periods=3, freq="ME")
    return pd.DataFrame(
        {
            "cape": [20.0, 20.0, last_cape],
            "spx_close": [100, 110, 120],
            "spx_10m_ma": [90, 100, 110],
            "above_10m_ma": [True, True, True],
            "return_12m": [0.1, 0.1, 0.1],
            "drawdown": [0.0, 0.0, 0.0],
            "baa_aaa_spread": [0.8, 0.8, 0.8],
            "baa_aaa_6m_change": [0.0, 0.0, 0.0],
            "hy_oas": [pd.NA, pd.NA, pd.NA],
            "sahm_gap": [0.1, 0.1, 0.1],
            "yield_curve": [1.0, 1.0, 1.0],
            "curve_inverted": [False, False, False],
            "curve_resteepening_after_inversion": [False, False, False],
            "real_yield_10y": [pd.NA, pd.NA, pd.NA],
        },
        index=idx,
    )


def test_future_cape_change_does_not_reclassify_prior_months(tmp_path):
    cfg = load_config("configs/config.yaml")
    a = classify_panel(make_panel(20), cfg).iloc[:2]["regime"].tolist()
    b = classify_panel(make_panel(42), cfg).iloc[:2]["regime"].tolist()
    assert a == b
