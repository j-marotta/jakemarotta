#!/usr/bin/env python3
"""Run a backtest.

Examples:
  python scripts/run_backtest.py --csv data/sample/SYNTH.csv
  python scripts/run_backtest.py --csv data/SPY.csv --strategy rsi_mean_reversion
  python scripts/run_backtest.py --schwab SPY --years 10
  python scripts/run_backtest.py --csv data/SPY.csv --fast 10 --slow 50 --trades
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.backtest import Backtester
from bot.data import fetch_schwab, load_csv
from bot.strategy import make_strategy


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="path to OHLCV CSV")
    src.add_argument("--schwab", metavar="SYMBOL", help="fetch history from Schwab (requires auth)")
    p.add_argument("--years", type=int, default=10, help="years of history for --schwab")
    p.add_argument("--strategy", default="sma_cross", choices=["sma_cross", "rsi_mean_reversion"])
    p.add_argument("--fast", type=int, help="fast SMA window (sma_cross)")
    p.add_argument("--slow", type=int, help="slow SMA window (sma_cross)")
    p.add_argument("--equity", type=float, default=100_000)
    p.add_argument("--slippage-bps", type=float, default=2.0)
    p.add_argument("--commission", type=float, default=0.0)
    p.add_argument("--trades", action="store_true", help="print the trade list")
    p.add_argument("--equity-out", help="write the equity curve to this CSV path")
    args = p.parse_args()

    if args.csv:
        df = load_csv(args.csv)
        source = args.csv
    else:
        from bot.schwab import SchwabClient
        df = fetch_schwab(SchwabClient(), args.schwab, years=args.years)
        source = f"Schwab:{args.schwab}"

    params = {}
    if args.strategy == "sma_cross":
        if args.fast:
            params["fast"] = args.fast
        if args.slow:
            params["slow"] = args.slow
    strategy = make_strategy(args.strategy, **params)

    bt = Backtester(
        initial_equity=args.equity,
        commission_per_trade=args.commission,
        slippage_bps=args.slippage_bps,
    )
    result = bt.run(df, strategy)

    print(f"\nBacktest: {strategy.name} on {source} ({len(df)} bars)")
    print(f"Params: {strategy}\n")
    print(result.metrics)

    if args.trades:
        print("\nTrades:")
        print(result.trades_frame().to_string(index=False))

    if args.equity_out:
        result.equity.to_csv(args.equity_out)
        print(f"\nEquity curve written to {args.equity_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
