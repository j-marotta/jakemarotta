"""Event-driven backtester.

Execution model (deliberately conservative, no lookahead):
  - The strategy signal at bar t is computed from data up to and including bar t.
  - Entries/exits triggered by that signal fill at bar t+1's OPEN, adjusted for
    slippage, minus commission.
  - An optional ATR trailing stop is evaluated intrabar: if bar t's low crosses
    the stop, the fill is at the stop price (or the open, if the bar gapped
    below the stop).
Long-only, whole shares, single symbol.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .metrics import Metrics, compute_metrics
from .strategy import Strategy


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str = ""

    @property
    def pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def pnl_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        return self.exit_price / self.entry_price - 1.0


@dataclass
class BacktestResult:
    equity: pd.Series
    position: pd.Series  # shares held at each bar close
    trades: list[Trade]
    metrics: Metrics

    def trades_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "entry_date": t.entry_date,
                    "exit_date": t.exit_date,
                    "shares": t.shares,
                    "entry_price": round(t.entry_price, 4),
                    "exit_price": round(t.exit_price, 4) if t.exit_price else None,
                    "pnl": round(t.pnl, 2),
                    "pnl_pct": round(t.pnl_pct * 100, 2),
                    "exit_reason": t.exit_reason,
                }
                for t in self.trades
            ]
        )


@dataclass
class Backtester:
    initial_equity: float = 100_000.0
    commission_per_trade: float = 0.0  # Schwab charges $0 for online equity trades
    slippage_bps: float = 2.0  # applied against you on every fill
    position_fraction: float = 0.95  # fraction of equity deployed per entry
    risk_free_rate: float = 0.0  # annualized, for Sharpe/Sortino

    def run(self, df: pd.DataFrame, strategy: Strategy) -> BacktestResult:
        required = {"open", "high", "low", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"data missing columns: {sorted(missing)}")
        if not df.index.is_monotonic_increasing:
            raise ValueError("data index must be sorted ascending by date")

        res = strategy.generate(df)
        signal = res.signal.reindex(df.index).fillna(0).astype(int)
        stop_dist = (
            res.stop_distance.reindex(df.index) if res.stop_distance is not None else None
        )

        opens = df["open"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        sig = signal.to_numpy()
        sd = stop_dist.to_numpy() if stop_dist is not None else None

        slip = self.slippage_bps / 10_000.0
        cash = self.initial_equity
        shares = 0
        stop_price = -np.inf
        trades: list[Trade] = []
        open_trade: Trade | None = None
        pending = 0  # target signal from the previous bar, to execute at this open

        n = len(df)
        equity = np.empty(n)
        position = np.empty(n, dtype=int)

        for i in range(n):
            date = df.index[i]

            # 1) Execute the previous bar's signal at this bar's open.
            if pending == 1 and shares == 0:
                fill = opens[i] * (1 + slip)
                qty = int((cash * self.position_fraction - self.commission_per_trade) // fill)
                if qty > 0:
                    cash -= qty * fill + self.commission_per_trade
                    shares = qty
                    open_trade = Trade(entry_date=date, entry_price=fill, shares=qty)
                    stop_price = (
                        fill - sd[i - 1] if sd is not None and not np.isnan(sd[i - 1]) else -np.inf
                    )
            elif pending == 0 and shares > 0:
                fill = opens[i] * (1 - slip)
                cash += shares * fill - self.commission_per_trade
                open_trade.exit_date = date
                open_trade.exit_price = fill
                open_trade.exit_reason = "signal"
                trades.append(open_trade)
                open_trade = None
                shares = 0
                stop_price = -np.inf

            # 2) Intrabar trailing stop check.
            if shares > 0 and stop_price > -np.inf and lows[i] <= stop_price:
                # If the bar gapped below the stop, fill at the open instead.
                fill = min(stop_price, opens[i]) * (1 - slip)
                cash += shares * fill - self.commission_per_trade
                open_trade.exit_date = date
                open_trade.exit_price = fill
                open_trade.exit_reason = "stop"
                trades.append(open_trade)
                open_trade = None
                shares = 0
                stop_price = -np.inf

            # 3) Ratchet the trailing stop up using this bar's data.
            if shares > 0 and sd is not None and not np.isnan(sd[i]):
                stop_price = max(stop_price, highs[i] - sd[i])

            equity[i] = cash + shares * closes[i]
            position[i] = shares
            pending = sig[i]

        # Mark any still-open trade closed at the final bar for reporting.
        if open_trade is not None:
            open_trade.exit_date = df.index[-1]
            open_trade.exit_price = closes[-1]
            open_trade.exit_reason = "end_of_data"
            trades.append(open_trade)

        equity_s = pd.Series(equity, index=df.index, name="equity")
        position_s = pd.Series(position, index=df.index, name="shares")
        metrics = compute_metrics(
            equity_s, trades, df["close"], position_s, risk_free_rate=self.risk_free_rate
        )
        return BacktestResult(equity=equity_s, position=position_s, trades=trades, metrics=metrics)
