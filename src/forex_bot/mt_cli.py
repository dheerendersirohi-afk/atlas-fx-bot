from __future__ import annotations

import argparse
import json
import sys

from .connectors.metatrader import (
    IndicatorSpec,
    build_mt4_indicator_script,
    build_mt5_demo_ea,
    build_mt5_indicator_script,
    load_metatrader_risk_controls,
    load_metatrader_terminal_config,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MetaTrader MT4/MT5 helper CLI.")
    parser.add_argument(
        "--credentials",
        default="config.live-connectors.example.json",
        help="Path to the live connector config JSON file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Show MetaTrader connector config summary")
    config_parser.add_argument("--platform", choices=["metatrader4", "metatrader5"], required=True)

    indicator_parser = subparsers.add_parser("indicator", help="Generate MT4/MT5 indicator probe script")
    indicator_parser.add_argument("--platform", choices=["metatrader4", "metatrader5"], required=True)
    indicator_parser.add_argument("--name", required=True, help="Indicator name: ima, irsi, iatr, imacd, icustom")
    indicator_parser.add_argument("--symbol", default="NULL")
    indicator_parser.add_argument("--timeframe", default="PERIOD_CURRENT")
    indicator_parser.add_argument("--period", type=int, default=14)
    indicator_parser.add_argument("--shift", type=int, default=0)
    indicator_parser.add_argument("--method", default="MODE_SMA")
    indicator_parser.add_argument("--price", default="PRICE_CLOSE")
    indicator_parser.add_argument("--fast", type=int, default=12)
    indicator_parser.add_argument("--slow", type=int, default=26)
    indicator_parser.add_argument("--signal", type=int, default=9)
    indicator_parser.add_argument("--mode", type=int, default=0)
    indicator_parser.add_argument("--bar-shift", dest="bar_shift", type=int, default=0)
    indicator_parser.add_argument("--custom-indicator", dest="custom_indicator", default="")
    indicator_parser.add_argument("--custom-inputs", dest="custom_inputs", default="")

    demo_ea_parser = subparsers.add_parser("demo-ea", help="Generate an MT5 demo EA scaffold with risk controls")
    demo_ea_parser.add_argument("--symbol", default="EURUSD")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "config":
            config = load_metatrader_terminal_config(args.credentials, args.platform, validate=False)
            print(f"platform={config.platform}")
            print(f"mode={config.mode}")
            print(f"integration_enabled={config.integration_enabled}")
            print(f"terminal_path={config.terminal_path}")
            print(f"server={config.server}")
            return

        if args.command == "demo-ea":
            risk = load_metatrader_risk_controls(args.credentials, "metatrader5")
            print(build_mt5_demo_ea(args.symbol, risk))
            return

        custom_inputs = tuple(item.strip() for item in args.custom_inputs.split(",") if item.strip())
        spec = IndicatorSpec(
            name=args.name,
            symbol=args.symbol,
            timeframe=args.timeframe,
            period=args.period,
            shift=args.shift,
            method=args.method,
            price=args.price,
            fast=args.fast,
            slow=args.slow,
            signal=args.signal,
            mode=args.mode,
            bar_shift=args.bar_shift,
            custom_indicator=args.custom_indicator,
            custom_inputs=custom_inputs,
        )

        if args.platform == "metatrader4":
            print(build_mt4_indicator_script(spec))
        else:
            print(build_mt5_indicator_script(spec))
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
