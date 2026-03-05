"""
alerts.py — Telegram notifications for the bot
"""

import logging
import requests
import config

logger = logging.getLogger(__name__)


def send_telegram(message: str):
    """Send a message to Telegram. Silently skips if not configured."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id"    : config.TELEGRAM_CHAT_ID,
        "text"       : message,
        "parse_mode" : "HTML"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.ok:
            logger.warning(f"Telegram send failed: {resp.text}")
    except Exception as e:
        logger.warning(f"Telegram error: {e}")


def alert_rebalance_start(regime_bullish: bool, n_buys: int, n_sells: int):
    emoji = "🟢" if regime_bullish else "🔴"
    msg = (
        f"{emoji} <b>Momentum Bot — Monthly Rebalance</b>\n"
        f"Regime (EMA200): {'BULLISH' if regime_bullish else 'BEARISH'}\n"
        f"Orders: {n_buys} buys | {n_sells} sells"
    )
    send_telegram(msg)


def alert_rebalance_done(results: list, portfolio_value: float):
    placed  = sum(1 for r in results if r.get("status") == "PLACED")
    failed  = sum(1 for r in results if r.get("status") == "FAILED")
    msg = (
        f"✅ <b>Rebalance Complete</b>\n"
        f"Orders placed: {placed} | Failed: {failed}\n"
        f"Portfolio value: ₹{portfolio_value:,.0f}"
    )
    send_telegram(msg)


def alert_kill_switch(drawdown_pct: float):
    msg = (
        f"🚨 <b>KILL SWITCH TRIGGERED</b>\n"
        f"Drawdown: {drawdown_pct:.1f}% exceeded limit {config.MAX_DRAWDOWN_PCT}%\n"
        f"All trading halted. Manual review required."
    )
    send_telegram(msg)


def alert_error(error_msg: str):
    msg = f"⚠️ <b>Bot Error</b>\n<code>{error_msg[:500]}</code>"
    send_telegram(msg)


def alert_market_bearish():
    msg = (
        f"🔴 <b>Regime Filter: BEARISH</b>\n"
        f"Nifty 50 is below EMA{config.EMA_WINDOW}.\n"
        f"Bot will sell all holdings and move to cash."
    )
    send_telegram(msg)
