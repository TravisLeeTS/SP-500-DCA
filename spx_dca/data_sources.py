"""Public data downloaders and monthly panel builder inputs."""
from __future__ import annotations

import logging
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

from .config import AppConfig
from .utils import month_end_index, write_metadata

LOGGER = logging.getLogger(__name__)
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def _read_fred_csv(series: str) -> pd.Series:
    url = FRED_CSV.format(series=quote(series))
    df = pd.read_csv(url)
    if df.empty:
        raise ValueError(f"FRED returned no data for {series}")
    date_col = df.columns[0]
    value_col = df.columns[1]
    values = pd.to_numeric(df[value_col].replace(".", pd.NA), errors="coerce")
    out = pd.Series(values.values, index=pd.to_datetime(df[date_col]), name=series)
    return out.dropna()


def fetch_fred_series(cfg: AppConfig, series: str, force: bool = False) -> pd.Series:
    """Fetch a FRED series, using data/raw cache when available."""
    path = cfg.raw_dir / f"fred_{series}.csv"
    if path.exists() and not force:
        df = pd.read_csv(path, parse_dates=["date"])
        return pd.Series(df[series].values, index=df["date"], name=series).dropna()
    LOGGER.info("Downloading FRED %s", series)
    s = _read_fred_csv(series)
    pd.DataFrame({"date": s.index, series: s.values}).to_csv(path, index=False)
    write_metadata(path, {"source": "FRED", "series": series, "url": FRED_CSV.format(series=series)})
    time.sleep(0.15)
    return s


def fetch_yahoo_spx(cfg: AppConfig, force: bool = False) -> pd.Series:
    """Fetch S&P 500 daily close from Yahoo chart API as fallback."""
    path = cfg.raw_dir / "yahoo_gspc.csv"
    if path.exists() and not force:
        df = pd.read_csv(path, parse_dates=["date"])
        return pd.Series(df["close"].values, index=df["date"], name="yahoo_spx").dropna()
    ticker = cfg.source("yahoo_spx") or "^GSPC"
    params = {"period1": 0, "period2": int(time.time()), "interval": "1d", "events": "history"}
    resp = requests.get(YAHOO_CHART.format(ticker=quote(ticker, safe="")), params=params, timeout=30)
    resp.raise_for_status()
    result = resp.json()["chart"]["result"][0]
    timestamps = pd.to_datetime(result["timestamp"], unit="s").normalize()
    quote_data = result["indicators"]["quote"][0]
    close = pd.Series(quote_data["close"], index=timestamps, name="yahoo_spx").dropna()
    pd.DataFrame({"date": close.index, "close": close.values}).to_csv(path, index=False)
    write_metadata(path, {"source": "Yahoo Finance chart API", "ticker": ticker})
    return close


def fetch_shiller_cape(cfg: AppConfig, force: bool = False) -> pd.Series:
    """Fetch monthly Shiller CAPE/PE10 data from Yale and cache it."""
    path = cfg.raw_dir / "shiller_cape.csv"
    if path.exists() and not force:
        df = pd.read_csv(path, parse_dates=["date"])
        return pd.Series(df["cape"].values, index=df["date"], name="cape").dropna()
    url = cfg.source("shiller_url")
    LOGGER.info("Downloading Shiller CAPE from %s", url)
    resp = requests.get(url, timeout=45)
    resp.raise_for_status()
    raw = pd.read_excel(BytesIO(resp.content), sheet_name="Data", header=7)
    # Yale file uses a fractional year column named Date and CAPE column named CAPE.
    cols = {str(c).strip(): c for c in raw.columns}
    date_col = cols.get("Date") or raw.columns[0]
    cape_col = cols.get("CAPE") or cols.get("CAPE.1")
    if cape_col is None:
        matches = [c for c in raw.columns if "cape" in str(c).lower()]
        if not matches:
            raise ValueError("Could not locate CAPE column in Shiller data")
        cape_col = matches[-1]
    vals = raw[[date_col, cape_col]].copy()
    vals.columns = ["raw_date", "cape"]
    vals["raw_date"] = pd.to_numeric(vals["raw_date"], errors="coerce")
    vals["cape"] = pd.to_numeric(vals["cape"], errors="coerce")
    vals = vals.dropna()
    years = vals["raw_date"].astype(int)
    months = ((vals["raw_date"] - years) * 100).round().astype(int).clip(1, 12)
    dates = pd.to_datetime({"year": years, "month": months, "day": 1}).dt.to_period("M").dt.to_timestamp("M")
    cape = pd.Series(vals["cape"].values, index=dates, name="cape").sort_index().dropna()
    pd.DataFrame({"date": cape.index, "cape": cape.values}).to_csv(path, index=False)
    write_metadata(path, {"source": "Robert Shiller/Yale", "url": url})
    return cape


def to_monthly(series: pd.Series, how: str = "last") -> pd.Series:
    """Convert daily/monthly series to calendar month-end values."""
    s = series.copy().sort_index()
    s.index = pd.to_datetime(s.index)
    if how == "mean":
        out = s.resample("ME").mean()
    else:
        out = s.resample("ME").last()
    out.index = month_end_index(out.index)
    return out


def fetch_all_raw(cfg: AppConfig, force: bool = False) -> dict[str, pd.Series]:
    """Download/cache all public inputs required by the core model."""
    fred = cfg.source("fred") or {}
    data: dict[str, pd.Series] = {}
    for key, series in fred.items():
        try:
            data[key] = fetch_fred_series(cfg, series, force=force)
        except Exception as exc:  # noqa: BLE001 - log and continue by design
            LOGGER.warning("Failed to fetch FRED %s (%s): %s", key, series, exc)
    try:
        data["cape"] = fetch_shiller_cape(cfg, force=force)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to fetch Shiller CAPE: %s", exc)
    # FRED SP500 is reproducible but starts later than 1970 in some mirrors.
    # If it does not cover the configured start, backfill earlier months from Yahoo.
    start_ts = pd.Period(cfg.start_date, "M").to_timestamp("M")
    needs_yahoo = "sp500" not in data or data["sp500"].empty or data["sp500"].index.min() > start_ts
    if needs_yahoo:
        try:
            yahoo = fetch_yahoo_spx(cfg, force=force)
            if "sp500" in data and not data["sp500"].empty:
                combined = yahoo.combine_first(data["sp500"]).sort_index()
                # Prefer FRED values wherever both sources exist.
                combined.loc[data["sp500"].index] = data["sp500"]
                data["sp500"] = combined.dropna().rename("SP500")
            else:
                data["sp500"] = yahoo.rename("SP500")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch Yahoo fallback: %s", exc)
    return data


def load_raw_or_fetch(cfg: AppConfig) -> dict[str, pd.Series]:
    """Load cache if present; otherwise download."""
    return fetch_all_raw(cfg, force=False)
