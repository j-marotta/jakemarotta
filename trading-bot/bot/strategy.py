"""Trading strategies.

A strategy consumes an OHLCV DataFrame and emits a target position signal per bar:
  +1 = long, 0 = flat. (Short selling is intentionally not supported.)

The signal at bar t may only use data up to and including bar t; the backtester
executes the resulting trade at bar t+1's open, so there is no lookahead bias.
"""

from dataclasses import dataclass, field

import pandas as pd

from .indicators import atr, rsi, sma


@dataclass
class StrategyResult:
    """Per-bar target signal plus optional per-bar stop distance (in price units)."""

    signal: pd.Series
    stop_distance: pd.Series | None = None


class Strategy:
    name = "base"

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        raise NotImplementedError


@dataclass
class SmaCross(Strategy):
    """Long when fast SMA > slow SMA, flat otherwise.

    Optional RSI filter blocks new entries when RSI is overbought, and an
    ATR-multiple stop distance is exposed for the backtester / live engine.
    """

    fast: int = 20
    slow: int = 100
    rsi_window: int = 14
    rsi_max_entry: float | None = 75.0  # block entries above this; None disables
    atr_window: int = 14
    atr_stop_mult: float | None = 3.0  # trailing stop = mult * ATR; None disables
    name: str = field(default="sma_cross", init=False)

    def __post_init__(self):
        if self.fast >= self.slow:
            raise ValueError(f"fast ({self.fast}) must be < slow ({self.slow})")

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        close = df["close"]
        fast = sma(close, self.fast)
        slow = sma(close, self.slow)

        raw = (fast > slow).astype(int)
        raw[fast.isna() | slow.isna()] = 0

        if self.rsi_max_entry is not None:
            r = rsi(close, self.rsi_window)
            # Block *new* entries while overbought, but don't force-exit an
            # existing long: forward-fill held state through blocked bars.
            entry_ok = (r <= self.rsi_max_entry) | r.isna()
            signal = raw.copy()
            holding = False
            vals = signal.to_numpy().copy()
            ok = entry_ok.to_numpy()
            for i in range(len(vals)):
                if vals[i] == 1 and not holding:
                    if ok[i]:
                        holding = True
                    else:
                        vals[i] = 0
                elif vals[i] == 0:
                    holding = False
            signal = pd.Series(vals, index=signal.index)
        else:
            signal = raw

        stop_dist = None
        if self.atr_stop_mult is not None:
            stop_dist = atr(df["high"], df["low"], close, self.atr_window) * self.atr_stop_mult

        return StrategyResult(signal=signal, stop_distance=stop_dist)


@dataclass
class RsiMeanReversion(Strategy):
    """Buy oversold dips in an uptrend; exit when RSI normalizes.

    Entry: RSI < oversold while close > trend SMA. Exit: RSI > exit_level.
    """

    rsi_window: int = 2
    oversold: float = 10.0
    exit_level: float = 60.0
    trend_window: int = 200
    atr_window: int = 14
    atr_stop_mult: float | None = 3.0
    name: str = field(default="rsi_mean_reversion", init=False)

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        close = df["close"]
        r = rsi(close, self.rsi_window)
        trend = sma(close, self.trend_window)

        enter = (r < self.oversold) & (close > trend)
        exit_ = r > self.exit_level

        vals = []
        holding = False
        for e, x in zip(enter.fillna(False), exit_.fillna(False)):
            if holding and x:
                holding = False
            elif not holding and e:
                holding = True
            vals.append(1 if holding else 0)
        signal = pd.Series(vals, index=df.index)

        stop_dist = None
        if self.atr_stop_mult is not None:
            stop_dist = atr(df["high"], df["low"], close, self.atr_window) * self.atr_stop_mult

        return StrategyResult(signal=signal, stop_distance=stop_dist)


STRATEGIES: dict[str, type[Strategy]] = {
    "sma_cross": SmaCross,
    "rsi_mean_reversion": RsiMeanReversion,
}


def make_strategy(name: str, **params) -> Strategy:
    try:
        cls = STRATEGIES[name]
    except KeyError:
        raise ValueError(f"unknown strategy {name!r}; available: {sorted(STRATEGIES)}")
    return cls(**params)
