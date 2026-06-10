import numpy as np
import pandas as pd
import pytest

from bot.backtest import Backtester
from bot.data import generate_synthetic
from bot.strategy import SmaCross, StrategyResult, Strategy


def make_df(closes, start="2024-01-01"):
    idx = pd.bdate_range(start=start, periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame(
        {"open": c.values, "high": c.values * 1.01, "low": c.values * 0.99,
         "close": c.values, "volume": 1_000_000},
        index=idx,
    )


class AlwaysLong(Strategy):
    name = "always_long"

    def generate(self, df):
        return StrategyResult(signal=pd.Series(1, index=df.index))


class FixedSignal(Strategy):
    name = "fixed"

    def __init__(self, signal):
        self._signal = signal

    def generate(self, df):
        return StrategyResult(signal=pd.Series(self._signal, index=df.index))


def test_entry_fills_at_next_open():
    # Signal turns on at bar 1; entry must fill at bar 2's open, not bar 1's.
    df = make_df([100, 100, 110, 110, 110])
    bt = Backtester(initial_equity=10_000, slippage_bps=0, position_fraction=1.0)
    res = bt.run(df, FixedSignal([0, 1, 1, 1, 1]))
    trade = res.trades[0]
    assert trade.entry_date == df.index[2]
    assert trade.entry_price == pytest.approx(110.0)


def test_no_lookahead_profit_on_step():
    # Price steps up AFTER the signal: bot enters at the new price, gains nothing.
    df = make_df([100] * 3 + [200] * 3)
    bt = Backtester(initial_equity=10_000, slippage_bps=0, position_fraction=1.0)
    res = bt.run(df, FixedSignal([0, 0, 1, 1, 1, 1]))
    # Entry at bar 3 open (200); price stays 200 → no profit from the jump.
    assert res.equity.iloc[-1] == pytest.approx(10_000.0)


def test_pnl_on_linear_ramp():
    df = make_df(np.linspace(100, 150, 20))
    bt = Backtester(initial_equity=10_000, slippage_bps=0, position_fraction=1.0)
    res = bt.run(df, AlwaysLong())
    entry = df["open"].iloc[1]
    shares = int(10_000 // entry)
    expected = 10_000 - shares * entry + shares * df["close"].iloc[-1]
    assert res.equity.iloc[-1] == pytest.approx(expected)


def test_slippage_and_commission_reduce_equity():
    df = make_df([100] * 10)
    base = Backtester(initial_equity=10_000, slippage_bps=0, commission_per_trade=0).run(
        df, AlwaysLong()
    )
    costly = Backtester(initial_equity=10_000, slippage_bps=20, commission_per_trade=5).run(
        df, AlwaysLong()
    )
    assert costly.equity.iloc[-1] < base.equity.iloc[-1]


def test_exit_on_signal_off():
    df = make_df([100, 100, 100, 120, 120, 120, 120])
    bt = Backtester(initial_equity=10_000, slippage_bps=0, position_fraction=1.0)
    res = bt.run(df, FixedSignal([1, 1, 1, 0, 0, 0, 0]))
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "signal"
    assert t.exit_date == df.index[4]  # signal off at bar 3 → exit at bar 4 open


def test_flat_when_no_signal():
    df = make_df([100] * 10)
    res = Backtester().run(df, FixedSignal([0] * 10))
    assert len(res.trades) == 0
    assert (res.equity == res.equity.iloc[0]).all()


def test_smacross_on_synthetic_runs_clean():
    df = generate_synthetic(start="2018-01-01", end="2023-12-31", seed=7)
    res = Backtester().run(df, SmaCross())
    assert res.equity.notna().all()
    assert (res.equity > 0).all()
    # Position is always whole shares and never negative (long-only).
    assert (res.position >= 0).all()


def test_smacross_validates_windows():
    with pytest.raises(ValueError):
        SmaCross(fast=50, slow=20)
