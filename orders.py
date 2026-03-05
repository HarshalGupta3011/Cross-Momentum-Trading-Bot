"""
orders.py — Order placement, tracking, and portfolio management via Kite Connect
"""

import os
import csv
import time
import logging
from datetime import datetime
from kiteconnect import KiteConnect
import config

logger = logging.getLogger(__name__)

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)


# ─────────────────────────────────────────────
# ORDER PLACEMENT
# ─────────────────────────────────────────────

def place_market_order(kite: KiteConnect, symbol: str, qty: int,
                       transaction_type: str) -> dict:
    """
    Place a market order on NSE.

    transaction_type: "BUY" or "SELL"
    Returns order result dict with order_id or error.
    """
    try:
        order_id = kite.place_order(
            variety    = KiteConnect.VARIETY_REGULAR,
            exchange   = KiteConnect.EXCHANGE_NSE,
            tradingsymbol = symbol,
            transaction_type = (KiteConnect.TRANSACTION_TYPE_BUY
                                if transaction_type == "BUY"
                                else KiteConnect.TRANSACTION_TYPE_SELL),
            quantity   = qty,
            product    = KiteConnect.PRODUCT_CNC,   # Cash & Carry (delivery)
            order_type = KiteConnect.ORDER_TYPE_MARKET,
        )

        result = {
            "timestamp"       : datetime.now().isoformat(),
            "symbol"          : symbol,
            "transaction_type": transaction_type,
            "quantity"        : qty,
            "order_id"        : order_id,
            "status"          : "PLACED",
            "error"           : ""
        }
        logger.info(f"  ✓ {transaction_type} {qty} x {symbol} → order_id: {order_id}")

    except Exception as e:
        result = {
            "timestamp"       : datetime.now().isoformat(),
            "symbol"          : symbol,
            "transaction_type": transaction_type,
            "quantity"        : qty,
            "order_id"        : "",
            "status"          : "FAILED",
            "error"           : str(e)
        }
        logger.error(f"  ✗ {transaction_type} {qty} x {symbol} FAILED: {e}")

    _log_order(result)
    return result


def execute_rebalance(kite: KiteConnect, buys: list, sells: list,
                       dry_run: bool = False) -> list:
    """
    Execute full rebalance: sell exits first, then buy entries.
    Sells first to free up cash.

    dry_run=True: log what WOULD happen but don't actually place orders.
    Returns list of order result dicts.
    """
    results = []

    if dry_run:
        logger.info("=== DRY RUN MODE — No real orders placed ===")

    # ── SELLS first ──
    if sells:
        logger.info(f"Placing {len(sells)} SELL orders...")
        for symbol, qty in sells:
            if dry_run:
                logger.info(f"  [DRY RUN] SELL {qty} x {symbol}")
                results.append({"symbol": symbol, "transaction_type": "SELL",
                                 "quantity": qty, "status": "DRY_RUN"})
            else:
                result = place_market_order(kite, symbol, qty, "SELL")
                results.append(result)
                time.sleep(0.3)   # Rate limit: ~3 orders/sec
    else:
        logger.info("No SELL orders needed.")

    # Brief pause to let sells settle before buying
    if sells and not dry_run:
        logger.info("Waiting 5s after sells before buying...")
        time.sleep(5)

    # ── BUYS ──
    if buys:
        logger.info(f"Placing {len(buys)} BUY orders...")
        for symbol, qty in buys:
            if dry_run:
                logger.info(f"  [DRY RUN] BUY {qty} x {symbol}")
                results.append({"symbol": symbol, "transaction_type": "BUY",
                                 "quantity": qty, "status": "DRY_RUN"})
            else:
                result = place_market_order(kite, symbol, qty, "BUY")
                results.append(result)
                time.sleep(0.3)
    else:
        logger.info("No BUY orders needed.")

    return results


# ─────────────────────────────────────────────
# PORTFOLIO STATE
# ─────────────────────────────────────────────

def get_current_holdings(kite: KiteConnect) -> dict:
    """
    Returns current holdings as {symbol: quantity} from Kite.
    Only includes stocks from our universe with qty > 0.
    """
    try:
        holdings = kite.holdings()
        result   = {}
        for h in holdings:
            sym = h["tradingsymbol"]
            qty = h["quantity"]
            if qty > 0 and sym in config.UNIVERSE:
                result[sym] = qty
        logger.info(f"Current holdings: {len(result)} stocks")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch holdings: {e}")
        return {}


def get_current_prices(kite: KiteConnect, symbols: list) -> dict:
    """
    Fetch last traded price for a list of symbols via Kite quote API.
    Returns {symbol: price}
    """
    if not symbols:
        return {}

    # Kite quote needs "NSE:SYMBOL" format
    instruments = [f"NSE:{s}" for s in symbols]

    try:
        quotes = kite.quote(instruments)
        prices = {}
        for key, data in quotes.items():
            symbol = key.replace("NSE:", "")
            prices[symbol] = data["last_price"]
        return prices
    except Exception as e:
        logger.error(f"Failed to fetch quotes: {e}")
        return {}


def get_portfolio_value(kite: KiteConnect) -> float:
    """
    Returns total current market value of our holdings.
    """
    holdings = get_current_holdings(kite)
    if not holdings:
        return 0.0

    prices = get_current_prices(kite, list(holdings.keys()))
    total  = sum(holdings[s] * prices.get(s, 0) for s in holdings)
    return total


# ─────────────────────────────────────────────
# DRAWDOWN KILL SWITCH
# ─────────────────────────────────────────────

def check_drawdown_kill_switch(current_value: float, peak_value: float) -> bool:
    """
    Returns True if drawdown exceeds MAX_DRAWDOWN_PCT → halt trading.
    """
    if peak_value <= 0:
        return False
    drawdown = (peak_value - current_value) / peak_value * 100
    if drawdown >= config.MAX_DRAWDOWN_PCT:
        logger.critical(
            f"⚠️  KILL SWITCH: Drawdown {drawdown:.1f}% exceeds limit "
            f"{config.MAX_DRAWDOWN_PCT}%. Halting all trading!"
        )
        return True
    return False


# ─────────────────────────────────────────────
# LOGGING HELPERS
# ─────────────────────────────────────────────

def _log_order(order: dict):
    """Append order to CSV log."""
    file_exists = os.path.exists(config.ORDER_LOG_FILE)
    os.makedirs(os.path.dirname(config.ORDER_LOG_FILE), exist_ok=True)
    with open(config.ORDER_LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=order.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(order)


def log_portfolio_snapshot(kite: KiteConnect, label: str = ""):
    """Save a snapshot of current holdings + values to CSV."""
    holdings = get_current_holdings(kite)
    if not holdings:
        return

    prices   = get_current_prices(kite, list(holdings.keys()))
    now      = datetime.now().isoformat()

    os.makedirs(os.path.dirname(config.PORTFOLIO_LOG_FILE), exist_ok=True)
    file_exists = os.path.exists(config.PORTFOLIO_LOG_FILE)

    with open(config.PORTFOLIO_LOG_FILE, "a", newline="") as f:
        fieldnames = ["timestamp", "label", "symbol", "quantity", "price", "value"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for sym, qty in holdings.items():
            price = prices.get(sym, 0)
            writer.writerow({
                "timestamp": now,
                "label"    : label,
                "symbol"   : sym,
                "quantity" : qty,
                "price"    : price,
                "value"    : qty * price
            })
    logger.info(f"Portfolio snapshot saved ({len(holdings)} positions).")
