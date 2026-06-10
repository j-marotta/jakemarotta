"""Charles Schwab API client (Trader API + Market Data API).

Setup (one-time):
  1. Create a developer account at https://developer.schwab.com and register an
     app with callback URL https://127.0.0.1:8182 (must match exactly).
     Request access to both "Accounts and Trading Production" and
     "Market Data Production". Approval can take a few days.
  2. Put the App Key and Secret in the environment (see .env.example):
       SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_CALLBACK_URL
  3. Run `python scripts/authorize.py` and follow the browser flow. Tokens are
     cached in token.json; access tokens auto-refresh. The refresh token
     expires after 7 days, after which you must re-run the authorize script.

API docs: https://developer.schwab.com/products
"""

import base64
import json
import os
import time
import urllib.parse
from pathlib import Path

import requests

API_BASE = "https://api.schwabapi.com"
AUTH_URL = f"{API_BASE}/v1/oauth/authorize"
TOKEN_URL = f"{API_BASE}/v1/oauth/token"


class SchwabAuthError(RuntimeError):
    pass


class SchwabClient:
    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        callback_url: str | None = None,
        token_path: str | Path = "token.json",
        timeout: float = 30.0,
    ):
        self.app_key = app_key or os.environ.get("SCHWAB_APP_KEY")
        self.app_secret = app_secret or os.environ.get("SCHWAB_APP_SECRET")
        self.callback_url = callback_url or os.environ.get(
            "SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182"
        )
        if not self.app_key or not self.app_secret:
            raise SchwabAuthError(
                "Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET (see .env.example)"
            )
        self.token_path = Path(token_path)
        self.timeout = timeout
        self._tokens: dict = {}
        if self.token_path.exists():
            self._tokens = json.loads(self.token_path.read_text())

    # ---------------- OAuth ----------------

    def authorization_url(self) -> str:
        params = urllib.parse.urlencode(
            {"client_id": self.app_key, "redirect_uri": self.callback_url}
        )
        return f"{AUTH_URL}?{params}"

    def exchange_code(self, redirected_url: str) -> None:
        """Complete the OAuth flow given the full URL Schwab redirected to."""
        qs = urllib.parse.urlparse(redirected_url).query
        code = urllib.parse.parse_qs(qs).get("code", [None])[0]
        if not code:
            raise SchwabAuthError("no ?code= parameter found in the pasted URL")
        self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.callback_url,
            }
        )

    def _refresh(self) -> None:
        refresh_token = self._tokens.get("refresh_token")
        if not refresh_token:
            raise SchwabAuthError("no refresh token; run scripts/authorize.py first")
        self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )

    def _token_request(self, data: dict) -> None:
        basic = base64.b64encode(f"{self.app_key}:{self.app_secret}".encode()).decode()
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=data,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise SchwabAuthError(f"token request failed ({resp.status_code}): {resp.text}")
        tokens = resp.json()
        tokens["obtained_at"] = time.time()
        self._tokens = tokens
        self.token_path.write_text(json.dumps(tokens, indent=2))

    def _access_token(self) -> str:
        if not self._tokens:
            raise SchwabAuthError("not authorized; run scripts/authorize.py first")
        age = time.time() - self._tokens.get("obtained_at", 0)
        # Access tokens last 30 minutes; refresh with a 60s safety margin.
        if age > self._tokens.get("expires_in", 1800) - 60:
            self._refresh()
        return self._tokens["access_token"]

    # ---------------- HTTP helpers ----------------

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token()}"
        resp = requests.request(
            method, f"{API_BASE}{path}", headers=headers, timeout=self.timeout, **kwargs
        )
        if resp.status_code == 401:
            # Token may have been revoked server-side; refresh once and retry.
            self._refresh()
            headers["Authorization"] = f"Bearer {self._tokens['access_token']}"
            resp = requests.request(
                method, f"{API_BASE}{path}", headers=headers, timeout=self.timeout, **kwargs
            )
        resp.raise_for_status()
        return resp

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        return self._request("GET", path, params=params).json()

    # ---------------- Market data ----------------

    def quote(self, symbol: str) -> dict:
        data = self._get(f"/marketdata/v1/{urllib.parse.quote(symbol)}/quotes")
        return data[symbol]

    def quotes(self, symbols: list[str]) -> dict:
        return self._get("/marketdata/v1/quotes", params={"symbols": ",".join(symbols)})

    def price_history(
        self,
        symbol: str,
        period_type: str = "year",
        period: int = 10,
        frequency_type: str = "daily",
        frequency: int = 1,
    ) -> list[dict]:
        """Returns a list of candle dicts: datetime (epoch ms), open/high/low/close/volume."""
        data = self._get(
            "/marketdata/v1/pricehistory",
            params={
                "symbol": symbol,
                "periodType": period_type,
                "period": period,
                "frequencyType": frequency_type,
                "frequency": frequency,
            },
        )
        return data.get("candles", [])

    # ---------------- Accounts & trading ----------------

    def account_numbers(self) -> list[dict]:
        """Each entry has 'accountNumber' and the 'hashValue' used in trading URLs."""
        return self._get("/trader/v1/accounts/accountNumbers")

    def account(self, account_hash: str, fields: str = "positions") -> dict:
        return self._get(f"/trader/v1/accounts/{account_hash}", params={"fields": fields})

    def place_order(self, account_hash: str, order: dict) -> str | None:
        """Submit an order. Returns the order ID parsed from the Location header."""
        resp = self._request(
            "POST",
            f"/trader/v1/accounts/{account_hash}/orders",
            json=order,
            headers={"Content-Type": "application/json"},
        )
        location = resp.headers.get("Location", "")
        return location.rstrip("/").split("/")[-1] or None

    def get_order(self, account_hash: str, order_id: str) -> dict:
        return self._get(f"/trader/v1/accounts/{account_hash}/orders/{order_id}")

    def cancel_order(self, account_hash: str, order_id: str) -> None:
        self._request("DELETE", f"/trader/v1/accounts/{account_hash}/orders/{order_id}")


def market_order(symbol: str, quantity: int, instruction: str) -> dict:
    """Build a simple market-order payload. instruction: 'BUY' or 'SELL'."""
    if instruction not in ("BUY", "SELL"):
        raise ValueError("instruction must be BUY or SELL")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    return {
        "orderType": "MARKET",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": instruction,
                "quantity": quantity,
                "instrument": {"symbol": symbol, "assetType": "EQUITY"},
            }
        ],
    }
