"""
config.py — All settings for the Momentum Bot
Edit this file before running the bot.
"""

# ─────────────────────────────────────────────
# ZERODHA KITE API CREDENTIALS
# Get these from: https://developers.kite.trade/
# ─────────────────────────────────────────────
KITE_API_KEY    = "your_api_key_here"
KITE_API_SECRET = "your_api_secret_here"

# ─────────────────────────────────────────────
# ZERODHA LOGIN CREDENTIALS (for auto-login)
# ─────────────────────────────────────────────
ZERODHA_USER_ID  = "your_zerodha_user_id"   # e.g. "AB1234"
ZERODHA_PASSWORD = "your_zerodha_password"

# TOTP Secret — get this from Zerodha:
#   1. Log in to zerodha.com → My Profile → Security → 2FA
#   2. Click "Show QR" → then "Can't scan? Use text key instead"
#   3. Copy that text key and paste it here
ZERODHA_TOTP_SECRET = "your_totp_secret_key_here"   # e.g. "JBSWY3DPEHPK3PXP"

# After first login, the access token is saved to this file automatically
ACCESS_TOKEN_FILE = "access_token.txt"

# ─────────────────────────────────────────────
# CAPITAL & POSITION SIZING
# ─────────────────────────────────────────────
TOTAL_CAPITAL   = 1_000_000   # Rs 10 Lakhs — CHANGE THIS
TOP_N           = 30          # Max stocks to hold
EXIT_RANK       = 34          # Exit if momentum rank drops below this
MOMENTUM_WINDOW = 252         # 1-year momentum lookback (trading days)
EMA_WINDOW      = 200         # Regime filter: EMA period on Nifty 50

# ─────────────────────────────────────────────
# RISK MANAGEMENT
# ─────────────────────────────────────────────
MAX_DRAWDOWN_PCT     = 20.0   # Kill switch: halt if portfolio drops >20% from peak
MAX_POSITION_PCT     = 0.05   # Max 5% in any single stock (safety cap)
MIN_STOCK_PRICE      = 50     # Skip stocks below this price (illiquid)
MIN_VOLUME           = 50000  # Skip stocks with avg volume below this

# ─────────────────────────────────────────────
# TELEGRAM ALERTS (optional)
# Leave blank to disable
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = ""       # e.g. "123456:ABCdef..."
TELEGRAM_CHAT_ID   = ""       # e.g. "-1001234567890"

# ─────────────────────────────────────────────
# NIFTY 500 UNIVERSE (NSE symbols, no .NS suffix for Kite)
# ─────────────────────────────────────────────
UNIVERSE = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK",
    "BHARTIARTL","SBIN","WIPRO","HCLTECH","LT",
    "AXISBANK","KOTAKBANK","ASIANPAINT","MARUTI","BAJFINANCE",
    "TITAN","SUNPHARMA","NESTLEIND","ULTRACEMCO","POWERGRID",
    "NTPC","COALINDIA","ONGC","TATAMOTORS","ADANIENT",
    "BAJAJFINSV","DIVISLAB","DRREDDY","CIPLA","EICHERMOT",
    "HEROMOTOCO","HINDALCO","JSWSTEEL","M&M","TECHM",
    "BRITANNIA","GRASIM","INDUSINDBK","ITC","PIDILITIND",
    "HAVELLS","MCDOWELL-N","DABUR","BERGEPAINT","COLPAL",
    "TATACONSUM","AMBUJACEM","GODREJCP","MARICO","VOLTAS",
    "APOLLOHOSP","FORTIS","MAXHEALTH","LALPATHLAB","METROPOLIS",
    "ZOMATO","NYKAA","DELHIVERY","IRCTC","RVNL",
    "IRFC","PFC","RECLTD","HDFCLIFE","SBILIFE",
    "ICICIGI","BAJAJ-AUTO","ESCORTS","APLAPOLLO","ASTRAL",
    "POLYCAB","KEI","CUMMINSIND","SIEMENS","ABB",
    "BHEL","HAL","BEL","MPHASIS","LTIM",
    "PERSISTENT","COFORGE","KPITTECH","TRENT","DMART",
    "PAGEIND","CONCOR","ADANIPORTS","INDIGO","BANKBARODA",
    "PNB","FEDERALBNK","IDFCFIRSTB","BANDHANBNK","MUTHOOTFIN",
    "CHOLAFIN","MANAPPURAM","TATASTEEL","SAIL","NMDC",
]

NIFTY50_SYMBOL  = "NIFTY 50"   # As used in Kite indices
NIFTY50_YFTICKER = "^NSEI"     # For historical data via yfinance

# ─────────────────────────────────────────────
# SCHEDULING
# ─────────────────────────────────────────────
# Rebalance runs on last trading day of each month
REBALANCE_HOUR   = 9    # 9:30 AM IST
REBALANCE_MINUTE = 30

# Daily login refresh time
LOGIN_HOUR   = 8
LOGIN_MINUTE = 0

# Log file paths
ORDER_LOG_FILE    = "logs/orders.csv"
PORTFOLIO_LOG_FILE = "logs/portfolio.csv"
BOT_LOG_FILE      = "logs/bot.log"
