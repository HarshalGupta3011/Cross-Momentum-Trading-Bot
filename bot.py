"""
bot.py — Main entry point for the Zerodha Momentum Bot

Runs as a long-lived process. Wakes up on the last trading day
of each month at the configured time and executes the rebalance.

Usage:
    python bot.py              # Live trading mode
    python bot.py --dry-run    # Simulate without placing orders
    python bot.py --now        # Force rebalance immediately (for testing)
"""

import os
import sys
import logging
import argparse
import schedule
import time
from datetime import datetime, date
import pandas as pd

import config
from login import get_kite_client
from signals import (fetch_prices, fetch_nifty50, is_market_bullish,
                     get_target_portfolio, compute_trade_list)
from orders import (execute_rebalance, get_current_holdings,
                    get_current_prices, get_portfolio_value,
                    check_drawdown_kill_switch, log_portfolio_snapshot)
from alerts import (alert_rebalance_start, alert_rebalance_done,
                    alert_kill_switch, alert_error, alert_market_bearish)

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(config.BOT_LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global state
_peak_portfolio_value = 0.0
_kill_switch_triggered = False


# ─────────────────────────────────────────────
# TRADING CALENDAR HELPERS
# ─────────────────────────────────────────────

def is_last_trading_day_of_month():
    """
    Returns True if today is the last trading day of the current month.
    Uses a simple heuristic: last weekday of the month.
    For production, replace with NSE holiday calendar.
    """
    today = date.today()

    # Get last day of month
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)

    last_day = next_month - pd.Timedelta(days=1)

    # Walk back to find last weekday
    while last_day.weekday() >= 5:  # 5=Sat, 6=Sun
        last_day = last_day - pd.Timedelta(days=1)

    return today == last_day


def is_market_hours():
    """Returns True if current time is within NSE trading hours (9:15–15:30 IST)."""
    now = datetime.now()
    market_open  = now.replace(hour=9,  minute=15, second=0)
    market_close = now.replace(hour=15, minute=30, second=0)
    return market_open <= now <= market_close


# ─────────────────────────────────────────────
# CORE REBALANCE LOGIC
# ─────────────────────────────────────────────

def run_rebalance(dry_run: bool = False, force: bool = False):
    """
    Full monthly rebalance:
    1. Check regime filter (EMA 200)
    2. Compute momentum scores
    3. Determine target portfolio
    4. Execute trades
    """
    global _peak_portfolio_value, _kill_switch_triggered

    logger.info("=" * 60)
    logger.info(f"  REBALANCE STARTING {'(DRY RUN)' if dry_run else '(LIVE)'}")
    logger.info("=" * 60)

    # Guard: only run on last trading day unless forced
    if not force and not is_last_trading_day_of_month():
        logger.info("Not the last trading day of month. Skipping.")
        return

    # Guard: only run during market hours unless forced
    if not force and not is_market_hours():
        logger.warning("Outside market hours. Skipping.")
        return

    # Guard: kill switch
    if _kill_switch_triggered:
        logger.critical("Kill switch is active. Rebalance blocked.")
        return

    try:
        # ── Step 1: Connect ──
        kite = get_kite_client()

        # ── Step 2: Portfolio value & drawdown check ──
        current_value = get_portfolio_value(kite)
        if current_value > 0:
            _peak_portfolio_value = max(_peak_portfolio_value, current_value)
            if check_drawdown_kill_switch(current_value, _peak_portfolio_value):
                _kill_switch_triggered = True
                alert_kill_switch(
                    (_peak_portfolio_value - current_value) / _peak_portfolio_value * 100
                )
                return

        # ── Step 3: Regime check ──
        logger.info("Checking regime filter (EMA 200)...")
        nifty50_prices = fetch_nifty50(days=400)
        regime_bullish = is_market_bullish(nifty50_prices, ema_window=config.EMA_WINDOW)

        current_holdings = get_current_holdings(kite)

        if not regime_bullish:
            # Market is bearish — sell everything, go to cash
            alert_market_bearish()
            if current_holdings:
                logger.info("BEARISH REGIME — Selling all holdings.")
                sells = list(current_holdings.items())
                buys  = []
                alert_rebalance_start(regime_bullish, 0, len(sells))
                results = execute_rebalance(kite, buys, sells, dry_run=dry_run)
                portfolio_value = get_portfolio_value(kite)
                alert_rebalance_done(results, portfolio_value)
            else:
                logger.info("BEARISH REGIME — Already in cash. Nothing to do.")
            return

        # ── Step 4: Fetch prices & compute signals ──
        logger.info("Fetching historical prices for momentum calculation...")
        prices = fetch_prices(config.UNIVERSE, days=420)

        logger.info("Computing momentum scores and target portfolio...")
        target_portfolio, ranks = get_target_portfolio(
            prices,
            list(current_holdings.keys()),
            top_n=config.TOP_N,
            exit_rank=config.EXIT_RANK
        )

        # ── Step 5: Compute trades ──
        all_symbols   = list(set(list(current_holdings.keys()) + target_portfolio))
        current_prices = get_current_prices(kite, all_symbols)

        buys, sells = compute_trade_list(
            current_holdings,
            target_portfolio,
            current_prices,
            config.TOTAL_CAPITAL
        )

        logger.info(f"Trade plan: {len(buys)} buys, {len(sells)} sells")
        for sym, qty in buys:
            logger.info(f"  BUY  {qty:5d} x {sym:20s} @ ₹{current_prices.get(sym, 0):,.2f}")
        for sym, qty in sells:
            logger.info(f"  SELL {qty:5d} x {sym:20s} @ ₹{current_prices.get(sym, 0):,.2f}")

        # ── Step 6: Execute ──
        alert_rebalance_start(regime_bullish, len(buys), len(sells))
        results = execute_rebalance(kite, buys, sells, dry_run=dry_run)

        # ── Step 7: Post-trade snapshot ──
        if not dry_run:
            time.sleep(3)
            log_portfolio_snapshot(kite, label="post_rebalance")
            portfolio_value = get_portfolio_value(kite)
            _peak_portfolio_value = max(_peak_portfolio_value, portfolio_value)
        else:
            portfolio_value = current_value

        alert_rebalance_done(results, portfolio_value)

        logger.info("=" * 60)
        logger.info("  REBALANCE COMPLETE")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"Rebalance error: {e}")
        alert_error(str(e))


# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────

def run_scheduler(dry_run: bool = False):
    """
    Schedule the rebalance check to run daily at the configured time.
    The rebalance itself only executes on the last trading day of the month.
    """
    run_time = f"{config.REBALANCE_HOUR:02d}:{config.REBALANCE_MINUTE:02d}"
    logger.info(f"Scheduler started. Rebalance check runs daily at {run_time} IST.")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE TRADING'}")
    logger.info(f"Regime: EMA {config.EMA_WINDOW} | Top {config.TOP_N} | Exit rank {config.EXIT_RANK}")
    logger.info(f"Capital: ₹{config.TOTAL_CAPITAL:,.0f}")

    schedule.every().day.at(run_time).do(run_rebalance, dry_run=dry_run)

    while True:
        schedule.run_pending()
        time.sleep(30)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zerodha Cross-Sectional Momentum Bot")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate rebalance without placing real orders")
    parser.add_argument("--now", action="store_true",
                        help="Force rebalance right now (for testing)")
    args = parser.parse_args()

    if args.now:
        logger.info("--now flag: forcing immediate rebalance...")
        run_rebalance(dry_run=args.dry_run, force=True)
    else:
        run_scheduler(dry_run=args.dry_run)
