"""
signals.py — Compute momentum scores and regime filter

Uses Kite Connect for historical prices (same data source as live trading).
Kite client is passed in from bot.py — no separate login needed.
"""

import time
import logging
import pandas as pd
from datetime import date, timedelta
from kiteconnect import KiteConnect
import config

logger = logging.getLogger(__name__)

NIFTY50_TOKEN = 256265   # Standard Kite instrument token for Nifty 50 index


# ─────────────────────────────────────────────
# FETCH HISTORICAL PRICES
# ─────────────────────────────────────────────

def _get_instrument_tokens(kite: KiteConnect, symbols: list) -> dict:
    """Return {symbol: token} map for all symbols in one API call."""
    try:
        instruments = kite.instruments("NSE")
        token_map   = {
            i["tradingsymbol"]: i["instrument_token"]
            for i in instruments
            if i["instrument_type"] == "EQ"
        }
        result = {}
        for sym in symbols:
            if sym in token_map:
                result[sym] = token_map[sym]
            else:
                logger.warning(f"  Token not found for {sym}")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch instruments: {e}")
        return {}


def _fetch_ohlcv(kite: KiteConnect, token: int, symbol: str,
                 days: int) -> pd.Series | None:
    """Fetch daily close prices for one symbol from Kite."""
    to_date   = date.today().strftime("%Y-%m-%d")
    from_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        candles = kite.historical_data(
            instrument_token = token,
            from_date        = from_date,
            to_date          = to_date,
            interval         = "day",
            continuous       = False,
            oi               = False
        )
        if not candles:
            return None

        df = pd.DataFrame(candles)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = df.set_index("date")
        return df["close"].rename(symbol)

    except Exception as e:
        logger.warning(f"  Failed {symbol}: {e}")
        return None


def fetch_prices(kite: KiteConnect, symbols: list, days: int = 1500) -> pd.DataFrame:
    """
    Fetch historical daily close prices for all symbols via Kite.
    kite:    authenticated KiteConnect instance passed in from bot.py
    symbols: list of NSE symbols (no .NS suffix)
    days:    calendar days of history to fetch (420 = ~252 trading days + buffer)
    Returns: DataFrame — index=date, columns=symbols
    """
    logger.info(f"Fetching prices for {len(symbols)} symbols from Kite...")

    token_map = _get_instrument_tokens(kite, symbols)
    closes    = {}

    for i, sym in enumerate(symbols, 1):
        token = token_map.get(sym)
        if not token:
            continue
        series = _fetch_ohlcv(kite, token, sym, days)
        if series is not None and len(series) > 100:
            closes[sym] = series
        time.sleep(0.12)   # stay within Kite rate limit ~8 req/sec

    if not closes:
        raise ValueError("No price data fetched from Kite. Check credentials and universe.")

    prices = pd.DataFrame(closes)
    prices = prices.dropna(axis=1, thresh=int(len(prices) * 0.8))
    prices = prices.ffill(limit=5)

    logger.info(f"  Fetched {prices.shape[1]} symbols x {len(prices)} days")
    return prices


def fetch_nifty50(kite: KiteConnect, days: int = 420) -> pd.Series:
    """Fetch Nifty 50 index prices for regime filter."""
    to_date   = date.today().strftime("%Y-%m-%d")
    from_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        candles = kite.historical_data(
            instrument_token = NIFTY50_TOKEN,
            from_date        = from_date,
            to_date          = to_date,
            interval         = "day",
            continuous       = False,
            oi               = False
        )
        df = pd.DataFrame(candles)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = df.set_index("date")
        series = df["close"].rename("NIFTY50")
        logger.info(f"  Nifty 50: {len(series)} days fetched")
        return series

    except Exception as e:
        raise ValueError(f"Could not fetch Nifty 50 from Kite: {e}")


# ─────────────────────────────────────────────
# REGIME FILTER
# ─────────────────────────────────────────────

def is_market_bullish(nifty50_prices: pd.Series,
                      ema_window: int = config.EMA_WINDOW) -> bool:
    """Returns True if Nifty 50 is above its EMA — regime is bullish."""
    ema        = nifty50_prices.ewm(span=ema_window, adjust=False).mean()
    last_price = float(nifty50_prices.iloc[-1])
    last_ema   = float(ema.iloc[-1])
    bullish    = last_price > last_ema

    logger.info(
        f"Regime check — Nifty 50: {last_price:.1f} | "
        f"EMA{ema_window}: {last_ema:.1f} | "
        f"Market: {'BULLISH' if bullish else 'BEARISH'}"
    )
    return bullish


# ─────────────────────────────────────────────
# MOMENTUM SCORES
# ─────────────────────────────────────────────

def compute_momentum_scores(prices: pd.DataFrame,
                             window: int = config.MOMENTUM_WINDOW) -> pd.Series:
    """
    12-1 month momentum: return over [window] trading days skipping last 21 days.
    Skipping last month avoids short-term reversal effect.
    window = 252 trading days = ~12 months
    skip   = 21  trading days = ~1 month
    """
    if len(prices) < window + 21:
        logger.warning(f"Not enough data. Have {len(prices)} rows, need {window + 21}")
        skip     = min(21, len(prices) // 10)
        lookback = len(prices) - skip - 1
    else:
        skip     = 21
        lookback = window

    mom = prices.iloc[-1] / prices.iloc[-(lookback + skip)] - 1
    return mom  # pd.Series indexed by symbol


# ─────────────────────────────────────────────
# RANK & SELECT
# ─────────────────────────────────────────────

def get_target_portfolio(prices: pd.DataFrame,
                          current_holdings: dict,
                          top_n: int     = config.TOP_N,
                          exit_rank: int = config.EXIT_RANK):
    """
    Returns target list of symbols to hold after rebalance.
    Enter: rank <= top_n
    Stay:  currently held with rank <= exit_rank
    Exit:  currently held with rank > exit_rank
    """
    mom_scores  = compute_momentum_scores(prices)
    last_prices = prices.iloc[-1]
    eligible    = last_prices[last_prices >= config.MIN_STOCK_PRICE].index
    mom_scores  = mom_scores[mom_scores.index.isin(eligible)]
    ranks       = mom_scores.rank(ascending=False, method="first")

    enter  = set(ranks[ranks <= top_n].index.tolist())
    stay   = {s for s in current_holdings if s in ranks.index and ranks[s] <= exit_rank}
    target = list(enter | stay)

    if len(target) > top_n:
        target_ranks = ranks[ranks.index.isin(target)]
        target = target_ranks.nsmallest(top_n).index.tolist()

    top_display = ranks[ranks <= top_n].sort_values().head(10)
    logger.info(f"Top 10 by momentum rank:\n{top_display.to_string()}")
    logger.info(f"Target portfolio: {len(target)} stocks")

    return target, ranks


# ─────────────────────────────────────────────
# TRADE LIST
# ─────────────────────────────────────────────

def compute_trade_list(current_holdings: dict,
                        target_portfolio: list,
                        current_prices: dict,
                        capital: float):
    """
    Compute buys and sells to move from current to target portfolio.
    Returns:
      buys:  list of (symbol, quantity)
      sells: list of (symbol, quantity)
    """
    current_symbols = set(current_holdings.keys())
    target_symbols  = set(target_portfolio)

    sells = [(s, current_holdings[s]) for s in current_symbols - target_symbols
             if current_holdings[s] > 0]

    new_entries     = list(target_symbols - current_symbols)
    n_stocks        = len(target_symbols)
    per_stock_value = capital / n_stocks if n_stocks > 0 else 0

    buys = []
    for symbol in new_entries:
        price = current_prices.get(symbol)
        if not price or price <= 0:
            logger.warning(f"  Skipping {symbol} — no price data")
            continue
        qty = int(per_stock_value / price)
        if qty > 0:
            buys.append((symbol, qty))

    return buys, sells
