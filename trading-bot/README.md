# Schwab Trading Bot

A long-only equity trading bot with a backtesting engine and live execution
through the Charles Schwab Trader API.

> **Disclaimer:** This is software, not financial advice. Backtested results —
> especially on the bundled synthetic data — do not predict live performance.
> Past performance never guarantees future results. Start with dry-run mode,
> then paper-size positions, before risking real money.

## What's included

```
bot/
  indicators.py   SMA, EMA, RSI (Wilder), ATR
  strategy.py     SmaCross (trend following), RsiMeanReversion (dip buying)
  backtest.py     event-driven backtester: next-open fills, slippage,
                  commissions, ATR trailing stops, no lookahead bias
  metrics.py      CAGR, Sharpe, Sortino, max drawdown, win rate, profit factor…
  data.py         CSV / Schwab / yfinance loaders + synthetic data generator
  schwab.py       Schwab API client: OAuth2, quotes, price history, orders
  broker.py       PaperBroker (simulated) and SchwabBroker (live) behind one interface
  live.py         daily reconciliation engine (signal → at most one order)
scripts/
  run_backtest.py        backtest from CSV or Schwab data
  authorize.py           one-time Schwab OAuth flow
  run_live.py            one live trading cycle (dry-run by default)
  generate_sample_data.py
tests/                   14 tests incl. lookahead-bias and P&L correctness checks
```

## Quick start (no Schwab account needed)

```bash
cd trading-bot
pip install -r requirements.txt
python -m pytest tests/            # 14 tests should pass
python scripts/run_backtest.py --csv data/sample/SYNTH.csv
```

Sample output on the bundled 10-year synthetic series (a simulated bear-heavy
decade, buy & hold −21.9%):

```
Backtest: sma_cross on data/sample/SYNTH.csv (2608 bars)
  Total return       +1.38%
  Buy & hold return  -21.90%
  Max drawdown       -39.66%
  Trades             66
  Time in market     46.8%
```

Useful flags: `--strategy rsi_mean_reversion`, `--fast 10 --slow 50`,
`--trades` (print every trade), `--equity-out equity.csv`.

### Backtest on real data

The synthetic data only validates the engine. For meaningful results, use real
history — either from Schwab once you're authorized:

```bash
python scripts/run_backtest.py --schwab SPY --years 10
```

or locally via yfinance (`pip install yfinance`), saving to CSV first:

```python
from bot.data import fetch_yfinance
fetch_yfinance("SPY", "10y").to_csv("data/SPY.csv")
```

## Connecting to Charles Schwab

1. **Create a developer account** at [developer.schwab.com](https://developer.schwab.com)
   (separate from your brokerage login). Register an app with callback URL
   `https://127.0.0.1:8182` and request access to **Accounts and Trading
   Production** and **Market Data Production**. Approval typically takes a few
   business days — wait until the app status is "Ready for use".
2. **Set credentials** (copy `.env.example` to `.env` or export them):
   ```bash
   export SCHWAB_APP_KEY=...
   export SCHWAB_APP_SECRET=...
   ```
3. **Authorize**:
   ```bash
   python scripts/authorize.py
   ```
   Log in via the printed URL, then paste the redirect URL back. Tokens land in
   `token.json` (gitignored). Access tokens auto-refresh; the **refresh token
   expires every 7 days**, so re-run this script weekly.

## Going live

The live engine is built for daily-bar strategies: run it once per trading day
shortly after the open. Each run recomputes the signal on completed daily bars
(the same inputs the backtest saw), compares it to your actual position, and
submits at most one market order to reconcile.

```bash
# Dry run — prints the intended order, submits nothing (default):
python scripts/run_live.py --symbol SPY

# Paper trading (in-memory fills):
python scripts/run_live.py --symbol SPY --paper --execute

# Real orders against your Schwab account:
python scripts/run_live.py --symbol SPY --execute
```

Schedule with cron (9:45 AM ET, weekdays):

```cron
45 9 * * 1-5  cd /path/to/trading-bot && /usr/bin/python3 scripts/run_live.py --symbol SPY --execute >> bot.log 2>&1
```

## Strategies

- **`sma_cross`** (default): long when the 20-day SMA is above the 100-day SMA,
  with an RSI(14) > 75 overbought filter on new entries and a 3×ATR(14)
  trailing stop. Classic trend following: many small losses, occasional large
  wins, sits out downtrends.
- **`rsi_mean_reversion`**: buys RSI(2) < 10 dips when price is above the
  200-day SMA, exits when RSI(2) > 60. Short holds, high win rate, small wins.

Add your own by subclassing `Strategy` in `bot/strategy.py` and registering it
in `STRATEGIES` — the backtester and live engine both pick it up.

## Design notes

- **No lookahead:** signals computed on bar *t* execute at bar *t+1*'s open.
  `tests/test_backtest.py::test_no_lookahead_profit_on_step` proves the engine
  can't profit from information it doesn't have yet.
- **Costs modeled:** slippage (default 2 bps per side) and per-trade commission
  (default $0, matching Schwab's online equity pricing).
- **Long-only, whole shares, single symbol** — deliberately simple. Margin,
  shorting, and multi-asset portfolios are out of scope for v0.1.
- **Stateless live engine:** the brokerage account is the source of truth for
  positions, so a crashed or skipped run self-heals on the next cycle.
