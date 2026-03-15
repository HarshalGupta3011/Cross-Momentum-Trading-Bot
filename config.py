"""
config.py — All settings for the Momentum Bot
Edit this file before running the bot.
"""

import os
import requests
import pandas as pd
from datetime import date

# ─────────────────────────────────────────────
# ZERODHA KITE API CREDENTIALS
# ─────────────────────────────────────────────
KITE_API_KEY            = ""
KITE_API_SECRET         = ""
ACCESS_TOKEN_FILE       = "access_token.txt"

# ─────────────────────────────────────────────
# CAPITAL & POSITION SIZING
# ─────────────────────────────────────────────
TOTAL_CAPITAL           = 500000
TOP_N                   = 30
EXIT_RANK               = 34
MOMENTUM_WINDOW         = 252
EMA_WINDOW              = 200

# ─────────────────────────────────────────────
# RISK MANAGEMENT
# ─────────────────────────────────────────────
MAX_DRAWDOWN_PCT        = 20.0
MAX_POSITION_PCT        = 0.05
MIN_STOCK_PRICE         = 50
MIN_VOLUME              = 50000

# ─────────────────────────────────────────────
# TELEGRAM ALERTS (optional)
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN      = ""
TELEGRAM_CHAT_ID        = ""

# ─────────────────────────────────────────────
# NIFTY 500 UNIVERSE — fetched from NSE at startup
# ─────────────────────────────────────────────

def _fetch_nifty500() -> list:
    """
    Fetch official Nifty 500 constituents from NSE.
    Caches to logs/nifty500_cache.csv — refreshes once per day.
    Falls back to cache if NSE is unreachable.
    """
    cache_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    cache_file = os.path.join(cache_dir, "nifty500_cache.csv")
    os.makedirs(cache_dir, exist_ok=True)

    # Use cache if written today
    if os.path.exists(cache_file):
        file_date = date.fromtimestamp(os.path.getmtime(cache_file))
        if file_date >= date.today():
            try:
                df = pd.read_csv(cache_file)
                symbols = df["Symbol"].str.strip().tolist()
                if len(symbols) > 100:
                    return symbols
            except Exception:
                pass

    # Download from NSE
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer"   : "https://www.nseindia.com/",
        "Accept"    : "text/html,application/xhtml+xml,*/*",
    }
    urls = [
        "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
        "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    ]
    for url in urls:
        try:
            resp    = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            from io import StringIO
            df      = pd.read_csv(StringIO(resp.text))
            symbols = df["Symbol"].str.strip().tolist()
            if len(symbols) > 100:
                df.to_csv(cache_file, index=False)
                return symbols
        except Exception:
            continue

    # Stale cache fallback
    if os.path.exists(cache_file):
        try:
            return pd.read_csv(cache_file)["Symbol"].str.strip().tolist()
        except Exception:
            pass

    # Hard fallback — Nifty 50 only
    return [
        "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK",
        "BHARTIARTL","SBIN","WIPRO","HCLTECH","LT",
        "AXISBANK","KOTAKBANK","ASIANPAINT","MARUTI","BAJFINANCE",
        "TITAN","SUNPHARMA","NESTLEIND","ULTRACEMCO","POWERGRID",
        "NTPC","COALINDIA","ONGC","TATAMOTORS","ADANIENT",
        "BAJAJFINSV","DIVISLAB","DRREDDY","CIPLA","EICHERMOT",
        "HEROMOTOCO","HINDALCO","JSWSTEEL","M&M","TECHM",
        "BRITANNIA","GRASIM","INDUSINDBK","ITC","TATACONSUM",
        "HDFCLIFE","SBILIFE","ICICIGI","BAJAJ-AUTO","TRENT",
        "DMART","ADANIPORTS","INDIGO","TATASTEEL","LTM",
    ]


# Loaded once at import — available as config.UNIVERSE everywhere
UNIVERSE = _fetch_nifty500()

# ─────────────────────────────────────────────
# OTHER SETTINGS
# ─────────────────────────────────────────────
NIFTY50_SYMBOL   = "NIFTY 50"
NIFTY50_YFTICKER = "^NSEI"

REBALANCE_HOUR          = 9
REBALANCE_MINUTE        = 30
LOGIN_HOUR       = 8
LOGIN_MINUTE     = 0

ORDER_LOG_FILE     = "logs/orders.csv"
PORTFOLIO_LOG_FILE = "logs/portfolio.csv"
BOT_LOG_FILE       = "logs/bot.log"
