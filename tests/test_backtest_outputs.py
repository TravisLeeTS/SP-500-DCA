import pandas as pd

from spx_dca.backtest import add_forward_outcomes


def test_backtest_forward_columns_exist():
    idx = pd.date_range("2020-01-31", periods=40, freq="ME")
    df = pd.DataFrame({"spx_close": range(100, 140), "regime": "Green", "dca_amount_aed": 5000, "drawdown": 0.0}, index=idx)
    out = add_forward_outcomes(df)
    for col in ["forward_6m_return", "forward_12m_return", "max_dd_next_12m", "bad_12m"]:
        assert col in out.columns
