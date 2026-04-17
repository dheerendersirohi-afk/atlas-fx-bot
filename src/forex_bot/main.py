from __future__ import annotations

import argparse
import json

from .config import load_config
from .engine import TradingEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the forex trading bot on CSV market data.")
    parser.add_argument("--config", required=True, help="Path to the bot config JSON file")
    parser.add_argument("--data", required=True, help="Path to historical market data CSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    engine = TradingEngine(config=config)
    summary = engine.run_csv(args.data)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
