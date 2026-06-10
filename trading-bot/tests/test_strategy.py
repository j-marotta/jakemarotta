import pandas as pd

from bot.data import generate_synthetic
from bot.strategy import RsiMeanReversion, SmaCross, make_strategy


def test_signals_are_binary_and_aligned():
    df = generate_synthetic(start="2019-01-01", end="2022-12-31", seed=3)
    for strat in (SmaCross(), RsiMeanReversion()):
        res = strat.generate(df)
        assert res.signal.index.equals(df.index)
        assert set(res.signal.unique()) <= {0, 1}
        if res.stop_distance is not None:
            assert res.stop_distance.index.equals(df.index)


def test_sma_cross_warmup_is_flat():
    df = generate_synthetic(start="2019-01-01", end="2020-12-31", seed=5)
    res = SmaCross(fast=20, slow=100).generate(df)
    assert (res.signal.iloc[:99] == 0).all()


def test_make_strategy():
    s = make_strategy("sma_cross", fast=10, slow=50)
    assert s.fast == 10 and s.slow == 50
    try:
        make_strategy("nope")
        assert False, "should have raised"
    except ValueError:
        pass
