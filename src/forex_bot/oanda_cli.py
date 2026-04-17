from __future__ import annotations

import argparse
import json
import sys

from .connectors.oanda import OandaApiError, OandaClient, load_oanda_credentials


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OANDA REST-v20 helper CLI.")
    parser.add_argument(
        "--credentials",
        default="config.live-connectors.example.json",
        help="Path to the live connector config JSON file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("account", help="Fetch OANDA account summary")

    prices_parser = subparsers.add_parser("prices", help="Fetch current prices")
    prices_parser.add_argument("--instruments", required=True, help="Comma-separated instruments like EUR_USD,GBP_USD")

    order_parser = subparsers.add_parser("order", help="Place a market order")
    order_parser.add_argument("--instrument", required=True, help="Instrument like EUR_USD")
    order_parser.add_argument("--units", required=True, type=int, help="Positive for buy, negative for sell")
    order_parser.add_argument("--stop-loss", dest="stop_loss", help="Optional stop loss price")
    order_parser.add_argument("--take-profit", dest="take_profit", help="Optional take profit price")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        credentials = load_oanda_credentials(args.credentials)
        client = OandaClient(credentials)

        if args.command == "account":
            result = client.get_account_summary()
        elif args.command == "prices":
            instruments = [item.strip() for item in args.instruments.split(",") if item.strip()]
            if not instruments:
                raise OandaApiError("Provide at least one instrument for the prices command.")
            result = client.get_prices(instruments)
        else:
            if args.units == 0:
                raise OandaApiError("Order units must be non-zero.")
            result = client.place_market_order(
                instrument=args.instrument,
                units=args.units,
                stop_loss_price=args.stop_loss,
                take_profit_price=args.take_profit,
            )

        print(json.dumps(result, indent=2))
    except (OandaApiError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
