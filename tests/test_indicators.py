import pandas as pd

from spx_dca.data_sources import to_monthly


def test_to_monthly_uses_month_end_close():
    s = pd.Series([1, 2, 3], index=pd.to_datetime(["2020-01-01", "2020-01-31", "2020-02-03"]))
    out = to_monthly(s)
    assert out.loc[pd.Timestamp("2020-01-31")] == 2
    assert out.loc[pd.Timestamp("2020-02-29")] == 3
