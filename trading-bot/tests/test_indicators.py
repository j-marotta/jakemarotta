import numpy as np
import pandas as pd
import pytest

from bot.indicators import atr, rsi, sma


def test_sma_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert np.isnan(out.iloc[0]) and np.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(2.0)
    assert out.iloc[4] == pytest.approx(4.0)


def test_rsi_bounds_and_direction():
    up = pd.Series(np.linspace(100, 200, 50))
    down = pd.Series(np.linspace(200, 100, 50))
    assert rsi(up, 14).iloc[-1] == pytest.approx(100.0)
    assert rsi(down, 14).iloc[-1] == pytest.approx(0.0, abs=1e-6)
    mixed = pd.Series(100 + np.sin(np.arange(100)))
    r = rsi(mixed, 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_atr_positive():
    n = 50
    rng = np.random.default_rng(0)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, n)))
    high = close + 1.0
    low = close - 1.0
    out = atr(high, low, close, 14).dropna()
    assert (out > 0).all()
