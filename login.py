"""
login.py — Zerodha login handler

Automatically uses auto_login.py (TOTP-based, fully hands-free).
Falls back to manual login if auto_login fails.
"""

import logging
import sys
from kiteconnect import KiteConnect
import config

logger = logging.getLogger(__name__)


def get_kite_client() -> KiteConnect:
    """Return an authenticated KiteConnect instance using auto-login."""
    try:
        from auto_login import auto_login
        return auto_login()
    except Exception as e:
        logger.warning(f"Auto-login failed ({e}), falling back to manual login...")
        return _manual_login()


def _manual_login() -> KiteConnect:
    """Fallback: manual request_token entry."""
    import json, os
    from datetime import date

    kite      = KiteConnect(api_key=config.KITE_API_KEY)
    login_url = kite.login_url()

    print("\n" + "="*60)
    print("  MANUAL LOGIN REQUIRED")
    print("="*60)
    print(f"\n1. Open this URL:\n\n   {login_url}\n")
    print("2. Log in and copy the request_token from the redirect URL.\n")

    request_token = input("Paste request_token here: ").strip()

    session      = kite.generate_session(request_token, api_secret=config.KITE_API_SECRET)
    access_token = session["access_token"]
    kite.set_access_token(access_token)

    os.makedirs(os.path.dirname(config.ACCESS_TOKEN_FILE) or ".", exist_ok=True)
    with open(config.ACCESS_TOKEN_FILE, "w") as f:
        json.dump({"date": str(date.today()), "access_token": access_token}, f)

    logger.info("✓ Manual login successful.")
    return kite


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    kite    = get_kite_client()
    profile = kite.profile()
    print(f"\n✓ Logged in as: {profile['user_name']} ({profile['user_id']})")
