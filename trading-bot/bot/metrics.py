"""Performance metrics computed from an equity curve and trade list."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class Metrics:
    start: str
    end: str
    bars: int
    initial_equity: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    volatility_pct: float
    num_trades: int
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    exposure_pct: float
    buy_hold_return_pct: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()

    def __str__(self) -> str:
        rows = [
            ("Period", f"{self.start} → {self.end} ({self.bars} bars)"),
            ("Initial equity", f"${self.initial_equity:,.2f}"),
            ("Final equity", f"${self.final_equity:,.2f}"),
            ("Total return", f"{self.total_return_pct:+.2f}%"),
            ("Buy & hold return", f"{self.buy_hold_return_pct:+.2f}%"),
            ("CAGR", f"{self.cagr_pct:+.2f}%"),
            ("Sharpe (ann.)", f"{self.sharpe:.2f}"),
            ("Sortino (ann.)", f"{self.sortino:.2f}"),
            ("Volatility (ann.)", f"{self.volatility_pct:.2f}%"),
            ("Max drawdown", f"{self.max_drawdown_pct:.2f}%"),
            ("Trades", f"{self.num_trades}"),
            ("Win rate", f"{self.win_rate_pct:.1f}%"),
            ("Avg win / loss", f"{self.avg_win_pct:+.2f}% / {self.avg_loss_pct:+.2f}%"),
            ("Profit factor", f"{self.profit_factor:.2f}"),
            ("Time in market", f"{self.exposure_pct:.1f}%"),
        ]
        width = max(len(k) for k, _ in rows)
        return "\n".join(f"  {k:<{width}}  {v}" for k, v in rows)


def compute_metrics(
    equity: pd.Series,
    trades: list,
    close: pd.Series,
    position: pd.Series,
    risk_free_rate: float = 0.0,
) -> Metrics:
    returns = equity.pct_change().dropna()
    n = len(equity)
    years = max(n / TRADING_DAYS, 1e-9)

    total_ret = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0 if equity.iloc[-1] > 0 else -1.0

    rf_daily = risk_free_rate / TRADING_DAYS
    excess = returns - rf_daily
    vol = returns.std(ddof=1)
    sharpe = float(excess.mean() / vol * np.sqrt(TRADING_DAYS)) if vol > 0 else 0.0
    downside = excess[excess < 0].std(ddof=1)
    sortino = (
        float(excess.mean() / downside * np.sqrt(TRADING_DAYS))
        if downside and downside > 0
        else 0.0
    )

    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    max_dd = float(drawdown.min())

    pnl_pcts = [t.pnl_pct for t in trades]
    wins = [p for p in pnl_pcts if p > 0]
    losses = [p for p in pnl_pcts if p <= 0]
    gross_win = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = -sum(t.pnl for t in trades if t.pnl <= 0)
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0

    return Metrics(
        start=str(equity.index[0].date()),
        end=str(equity.index[-1].date()),
        bars=n,
        initial_equity=float(equity.iloc[0]),
        final_equity=float(equity.iloc[-1]),
        total_return_pct=total_ret * 100,
        cagr_pct=cagr * 100,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown_pct=max_dd * 100,
        volatility_pct=float(vol * np.sqrt(TRADING_DAYS) * 100) if vol > 0 else 0.0,
        num_trades=len(trades),
        win_rate_pct=len(wins) / len(pnl_pcts) * 100 if pnl_pcts else 0.0,
        avg_win_pct=float(np.mean(wins)) * 100 if wins else 0.0,
        avg_loss_pct=float(np.mean(losses)) * 100 if losses else 0.0,
        profit_factor=profit_factor,
        exposure_pct=float((position != 0).mean()) * 100,
        buy_hold_return_pct=float(close.iloc[-1] / close.iloc[0] - 1.0) * 100,
    )
