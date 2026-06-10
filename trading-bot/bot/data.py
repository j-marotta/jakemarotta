"""Data loading: CSV files, Schwab price history, optional yfinance, and a
synthetic-data generator for offline development.

All loaders return a DataFrame indexed by DatetimeIndex with columns:
open, high, low, close, volume.
"""

from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.lower() for c in df.columns})
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"data missing columns: {sorted(missing)}")
    df = df[COLUMNS].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df.dropna()


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load OHLCV from CSV with a 'date' column (or first column parseable as dates)."""
    df = pd.read_csv(path)
    date_col = next((c for c in df.columns if c.lower() in ("date", "datetime", "timestamp")), df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)
    df.index.name = "date"
    return _normalize(df)


def fetch_schwab(client, symbol: str, years: int = 10) -> pd.DataFrame:
    """Fetch daily price history via an authenticated SchwabClient."""
    candles = client.price_history(symbol, period_type="year", period=min(years, 20),
                                   frequency_type="daily", frequency=1)
    if not candles:
        raise RuntimeError(f"Schwab returned no candles for {symbol}")
    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["datetime"], unit="ms")
    df = df.set_index("date")
    return _normalize(df)


def fetch_yfinance(symbol: str, period: str = "10y") -> pd.DataFrame:
    """Fetch daily history via yfinance (optional dependency; for local use)."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise ImportError("pip install yfinance to use this loader") from e
    df = yf.Ticker(symbol).history(period=period, auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance returned no data for {symbol}")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    return _normalize(df)


def generate_synthetic(
    start: str = "2016-01-04",
    end: str = "2025-12-31",
    initial_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Regime-switching geometric Brownian motion with plausible OHLC structure.

    For development and engine testing only — results on synthetic data say
    nothing about how a strategy will perform on real markets.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, end=end)
    n = len(dates)

    # Regimes: (annual drift, annual vol, mean duration in days)
    regimes = [(0.14, 0.13, 120), (0.02, 0.22, 60), (-0.25, 0.38, 35)]
    probs = [0.60, 0.28, 0.12]

    mu = np.empty(n)
    sigma = np.empty(n)
    i = 0
    while i < n:
        k = rng.choice(len(regimes), p=probs)
        m, s, dur = regimes[k]
        length = max(5, int(rng.exponential(dur)))
        j = min(n, i + length)
        mu[i:j] = m
        sigma[i:j] = s
        i = j

    dt = 1.0 / 252.0
    rets = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n)
    close = initial_price * np.exp(np.cumsum(rets))

    prev_close = np.concatenate([[initial_price], close[:-1]])
    gap = rng.normal(0, 0.25, n) * sigma * np.sqrt(dt)
    open_ = prev_close * np.exp(gap)
    intraday = np.abs(rng.normal(0, 0.6, n)) * sigma * np.sqrt(dt)
    high = np.maximum(open_, close) * np.exp(intraday)
    low = np.minimum(open_, close) * np.exp(-intraday)
    volume = (rng.lognormal(15, 0.4, n) * (1 + 2 * (sigma / 0.4))).astype(int)

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    df.index.name = "date"
    return df.round(4)
