#!/usr/bin/env python3
"""One-time Schwab OAuth flow. Re-run when the refresh token expires (every 7 days).

Usage:
  export SCHWAB_APP_KEY=... SCHWAB_APP_SECRET=...
  python scripts/authorize.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.schwab import SchwabClient


def main() -> int:
    client = SchwabClient()
    print("1. Open this URL in your browser and log in to Schwab:\n")
    print(f"   {client.authorization_url()}\n")
    print("2. After approving, your browser is redirected to your callback URL")
    print("   (the page won't load — that's fine). Copy the FULL URL from the")
    print("   address bar and paste it here.\n")
    redirected = input("Paste redirect URL: ").strip()
    client.exchange_code(redirected)
    print(f"\nSuccess. Tokens saved to {client.token_path}.")
    accounts = client.account_numbers()
    for a in accounts:
        print(f"  account ...{a['accountNumber'][-4:]}  hash={a['hashValue'][:12]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
