"""Broker abstraction: paper trading and live Schwab execution behind one interface."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .schwab import SchwabClient, market_order

log = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    shares: int
    avg_price: float


class Broker(ABC):
    @abstractmethod
    def get_position(self, symbol: str) -> Position | None: ...

    @abstractmethod
    def get_cash(self) -> float: ...

    @abstractmethod
    def buy(self, symbol: str, shares: int, ref_price: float) -> None: ...

    @abstractmethod
    def sell(self, symbol: str, shares: int, ref_price: float) -> None: ...


@dataclass
class PaperBroker(Broker):
    """Simulated fills at the reference price. State lives in memory only."""

    cash: float = 100_000.0
    positions: dict[str, Position] = field(default_factory=dict)

    def get_position(self, symbol: str) -> Position | None:
        return self.positions.get(symbol)

    def get_cash(self) -> float:
        return self.cash

    def buy(self, symbol: str, shares: int, ref_price: float) -> None:
        cost = shares * ref_price
        if cost > self.cash:
            raise ValueError(f"insufficient cash: need ${cost:,.2f}, have ${self.cash:,.2f}")
        self.cash -= cost
        pos = self.positions.get(symbol)
        if pos:
            total = pos.shares + shares
            pos.avg_price = (pos.avg_price * pos.shares + ref_price * shares) / total
            pos.shares = total
        else:
            self.positions[symbol] = Position(symbol, shares, ref_price)
        log.info("[paper] BUY %d %s @ %.2f", shares, symbol, ref_price)

    def sell(self, symbol: str, shares: int, ref_price: float) -> None:
        pos = self.positions.get(symbol)
        if not pos or pos.shares < shares:
            raise ValueError(f"cannot sell {shares} {symbol}: position is {pos}")
        self.cash += shares * ref_price
        pos.shares -= shares
        if pos.shares == 0:
            del self.positions[symbol]
        log.info("[paper] SELL %d %s @ %.2f", shares, symbol, ref_price)


class SchwabBroker(Broker):
    """Live execution through the Schwab Trader API using market orders."""

    def __init__(self, client: SchwabClient, account_hash: str | None = None):
        self.client = client
        if account_hash is None:
            accounts = client.account_numbers()
            if not accounts:
                raise RuntimeError("no Schwab accounts found for this login")
            account_hash = accounts[0]["hashValue"]
            log.info("using Schwab account ...%s", accounts[0]["accountNumber"][-4:])
        self.account_hash = account_hash

    def _account(self) -> dict:
        return self.client.account(self.account_hash)["securitiesAccount"]

    def get_position(self, symbol: str) -> Position | None:
        for p in self._account().get("positions", []):
            if p["instrument"].get("symbol") == symbol:
                shares = int(p.get("longQuantity", 0))
                if shares > 0:
                    return Position(symbol, shares, float(p.get("averagePrice", 0.0)))
        return None

    def get_cash(self) -> float:
        balances = self._account().get("currentBalances", {})
        return float(balances.get("cashAvailableForTrading", balances.get("cashBalance", 0.0)))

    def buy(self, symbol: str, shares: int, ref_price: float) -> None:
        order_id = self.client.place_order(self.account_hash, market_order(symbol, shares, "BUY"))
        log.info("[schwab] BUY %d %s submitted (order %s)", shares, symbol, order_id)

    def sell(self, symbol: str, shares: int, ref_price: float) -> None:
        order_id = self.client.place_order(self.account_hash, market_order(symbol, shares, "SELL"))
        log.info("[schwab] SELL %d %s submitted (order %s)", shares, symbol, order_id)
