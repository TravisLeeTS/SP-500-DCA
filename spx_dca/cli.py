"""Command-line interface for the S&P 500 DCA regime checker."""
from __future__ import annotations

import argparse
import logging

from .backtest import run_backtest
from .config import load_config
from .data_sources import fetch_all_raw
from .indicators import build_monthly_panel, load_monthly_panel
from .regime import classify_panel
from .report import make_all_reports, write_current_report, write_recent_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monthly S&P 500 DCA regime checker")
    parser.add_argument("--config", default="configs/config.yaml", help="Path to YAML config")
    parser.add_argument("--log-level", default="INFO", help="Python logging level")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch-data")
    sub.add_parser("build-panel")
    sub.add_parser("run-current")
    recent = sub.add_parser("run-recent")
    recent.add_argument("--months", type=int, default=12)
    bt = sub.add_parser("backtest")
    bt.add_argument("--start", default="1970-01")
    sub.add_parser("make-report")
    sub.add_parser("run-all")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    cfg = load_config(args.config)

    if args.command == "fetch-data":
        fetch_all_raw(cfg)
    elif args.command == "build-panel":
        build_monthly_panel(cfg)
    elif args.command == "run-current":
        panel = load_monthly_panel(cfg)
        regimes = classify_panel(panel, cfg)
        path = write_current_report(regimes, cfg)
        print(path)
    elif args.command == "run-recent":
        panel = load_monthly_panel(cfg)
        regimes = classify_panel(panel, cfg)
        path = write_recent_report(regimes, cfg, months=args.months)
        print(path)
    elif args.command == "backtest":
        panel = load_monthly_panel(cfg)
        run_backtest(panel, cfg, start=args.start)
    elif args.command == "make-report":
        for path in make_all_reports(cfg):
            print(path)
    elif args.command == "run-all":
        fetch_all_raw(cfg)
        build_monthly_panel(cfg)
        for path in make_all_reports(cfg):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
