"""Live trading engine.

Designed for a daily-bar strategy: run once per day shortly after the market
opens (e.g. via cron at 9:45 ET on weekdays). Each run:

  1. Pulls daily history for the symbol from Schwab.
  2. Recomputes the strategy signal on bars up to and including yesterday —
     identical inputs to what the backtester would have seen.
  3. Compares the target (long/flat) to the actual brokerage position and
     submits at most one market order to reconcile.

Safety: dry_run=True (the default) logs the intended order without submitting.
"""

import logging
from dataclasses import dataclass

import pandas as pd

from .broker import Broker
from .data import fetch_schwab
from .schwab import SchwabClient
from .strategy import Strategy

log = logging.getLogger(__name__)


@dataclass
class LiveEngine:
    client: SchwabClient
    broker: Broker
    strategy: Strategy
    symbol: str
    position_fraction: float = 0.95
    dry_run: bool = True

    def run_once(self) -> str:
        df = fetch_schwab(self.client, self.symbol, years=5)
        # Drop today's partial bar if present, so the signal only uses
        # completed bars — same information set as the backtest.
        today = pd.Timestamp.now().normalize()
        df = df[df.index < today]
        if len(df) < 250:
            raise RuntimeError(f"only {len(df)} bars of history for {self.symbol}")

        signal = int(self.strategy.generate(df).signal.iloc[-1])
        pos = self.broker.get_position(self.symbol)
        held = pos.shares if pos else 0
        quote = self.client.quote(self.symbol)
        price = float(quote["quote"]["lastPrice"])

        log.info(
            "%s: signal=%s held=%d last=%.2f (bar date %s)",
            self.symbol, "LONG" if signal else "FLAT", held, price, df.index[-1].date(),
        )

        if signal == 1 and held == 0:
            cash = self.broker.get_cash()
            shares = int(cash * self.position_fraction // price)
            if shares <= 0:
                return f"signal LONG but insufficient cash (${cash:,.2f})"
            if self.dry_run:
                return f"DRY RUN: would BUY {shares} {self.symbol} @ ~{price:.2f}"
            self.broker.buy(self.symbol, shares, price)
            return f"bought {shares} {self.symbol}"

        if signal == 0 and held > 0:
            if self.dry_run:
                return f"DRY RUN: would SELL {held} {self.symbol} @ ~{price:.2f}"
            self.broker.sell(self.symbol, held, price)
            return f"sold {held} {self.symbol}"

        return f"no action (signal={'LONG' if signal else 'FLAT'}, held={held})"
