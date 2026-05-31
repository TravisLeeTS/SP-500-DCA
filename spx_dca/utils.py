"""Shared utility helpers."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def month_end_index(index: pd.Index) -> pd.DatetimeIndex:
    """Normalize dates to calendar month-end timestamps."""
    return pd.to_datetime(index).to_period("M").to_timestamp("M")


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    """Write sidecar metadata as JSON with a UTC timestamp."""
    meta = {"created_at_utc": datetime.now(timezone.utc).isoformat(), **metadata}
    path.with_suffix(path.suffix + ".metadata.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )


def pct(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "missing"
    return f"{float(value) * 100:.{digits}f}%"


def num(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "missing"
    return f"{float(value):.{digits}f}"
