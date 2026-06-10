#!/usr/bin/env python3
"""Run one live trading cycle. Schedule with cron, e.g. weekdays at 9:45 ET:

  45 9 * * 1-5  cd /path/to/trading-bot && python scripts/run_live.py --symbol SPY

Defaults to DRY RUN (logs the intended order, submits nothing).
Pass --execute to place real orders, or --paper for in-memory paper trading.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.broker import PaperBroker, SchwabBroker
from bot.live import LiveEngine
from bot.schwab import SchwabClient
from bot.strategy import make_strategy


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", required=True)
    p.add_argument("--strategy", default="sma_cross", choices=["sma_cross", "rsi_mean_reversion"])
    p.add_argument("--paper", action="store_true", help="paper broker instead of Schwab account")
    p.add_argument("--execute", action="store_true",
                   help="actually submit orders (default is dry run)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    client = SchwabClient()
    broker = PaperBroker() if args.paper else SchwabBroker(client)
    engine = LiveEngine(
        client=client,
        broker=broker,
        strategy=make_strategy(args.strategy),
        symbol=args.symbol.upper(),
        dry_run=not args.execute,
    )
    print(engine.run_once())
    return 0


if __name__ == "__main__":
    sys.exit(main())
