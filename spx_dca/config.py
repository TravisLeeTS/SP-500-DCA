"""Configuration loading for the DCA regime checker."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("configs/config.yaml")


@dataclass(frozen=True)
class AppConfig:
    """Thin wrapper around YAML config with convenience accessors."""

    data: dict[str, Any]
    path: Path = DEFAULT_CONFIG_PATH

    @property
    def start_date(self) -> str:
        return str(self.data.get("start_date", "1970-01"))

    @property
    def macro_lag_months(self) -> int:
        return int(self.data.get("macro_lag_months", 1))

    @property
    def raw_dir(self) -> Path:
        return Path(self.data["paths"]["raw_dir"])

    @property
    def processed_dir(self) -> Path:
        return Path(self.data["paths"]["processed_dir"])

    @property
    def reports_dir(self) -> Path:
        return Path(self.data["paths"]["reports_dir"])

    @property
    def thresholds(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.data.get("thresholds", {}).items()}

    @property
    def dca_regimes(self) -> dict[str, dict[str, int]]:
        return self.data["dca"]["regimes"]

    def dca_default(self, regime: str) -> int:
        return int(self.dca_regimes[regime]["default_aed"])

    def dca_range(self, regime: str) -> tuple[int, int]:
        item = self.dca_regimes[regime]
        return int(item["min_aed"]), int(item["max_aed"])

    def source(self, name: str) -> Any:
        return self.data.get("sources", {}).get(name)


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Load YAML configuration and ensure output directories exist."""
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    cfg = AppConfig(data=data, path=cfg_path)
    for directory in [cfg.raw_dir, cfg.processed_dir, cfg.reports_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    return cfg
