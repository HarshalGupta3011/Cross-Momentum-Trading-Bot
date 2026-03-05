"""
signals.py — Compute momentum scores and regime filter

Uses yfinance to fetch historical prices for signal computation.
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# FETCH HISTORICAL PRICES
# ─────────────────────────────────────────────

def fetch_prices(symbols, days=400):
    """
    Fetch historical daily close prices for universe via yfinance.
    symbols: list of NSE symbols (without .NS)
    Returns: DataFrame with dates as index, symbols as columns
    """
    end   = datetime.today()
    start = end - timedelta(days=days)

    # yfinance needs .NS suffix for NSE stocks
    yf_tickers = [f"{s}.NS" for s in symbols]

    logger.info(f"Fetching prices for {len(yf_tickers)} symbols...")
    raw = yf.download(
        yf_tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        threads=True
    )["Close"]

    if isinstance(raw, pd.Series):
        raw = raw.to_frame()

    # Strip .NS from column names to match Kite symbols
    raw.columns = [c.replace(".NS", "") if isinstance(c, str) else c
                   for c in raw.columns]

    # Drop stocks with >20% missing
    raw = raw.dropna(axis=1, thresh=int(len(raw) * 0.8))
    raw = raw.ffill()

    logger.info(f"  ✓ {raw.shape[1]} symbols with sufficient data")
    return raw


def fetch_nifty50(days=400):
    """Fetch Nifty 50 index historical prices."""
    end   = datetime.today()
    start = end - timedelta(days=days)

    raw = yf.download(
        config.NIFTY50_YFTICKER,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False
    )["Close"]

    if isinstance(raw, pd.DataFrame):
        raw = raw.iloc[:, 0]
    return raw.squeeze()


# ─────────────────────────────────────────────
# REGIME FILTER
# ─────────────────────────────────────────────

def is_market_bullish(nifty50_prices, ema_window=config.EMA_WINDOW):
    """
    Returns True if Nifty 50 is above its EMA — regime is bullish.
    """
    ema  = nifty50_prices.ewm(span=ema_window, adjust=False).mean()
    last_price = float(nifty50_prices.iloc[-1])
    last_ema   = float(ema.iloc[-1])
    bullish    = last_price > last_ema

    logger.info(
        f"Regime check — Nifty 50: {last_price:.1f} | "
        f"EMA{ema_window}: {last_ema:.1f} | "
        f"Market: {'BULLISH ✓' if bullish else 'BEARISH ✗'}"
    )
    return bullish


# ─────────────────────────────────────────────
# MOMENTUM SCORES
# ─────────────────────────────────────────────

def compute_momentum_scores(prices, window=config.MOMENTUM_WINDOW):
    """
    12-1 month momentum: 12m return skipping the most recent month.
    Skipping last month avoids short-term reversal effect.
    """
    # Need at least window + 21 days of data
    if len(prices) < window + 21:
        logger.warning(f"Not enough data for momentum. Have {len(prices)} rows, need {window+21}")
        # Fall back to whatever we have
        skip = min(21, len(prices) // 10)
        lookback = len(prices) - skip - 1
    else:
        skip     = 21   # ~1 month
        lookback = window

    mom = prices.iloc[-1] / prices.iloc[-(lookback + skip)] - 1
    return mom  # pd.Series indexed by symbol


# ─────────────────────────────────────────────
# RANK & SELECT
# ─────────────────────────────────────────────

def get_target_portfolio(prices, current_holdings,
                          top_n=config.TOP_N,
                          exit_rank=config.EXIT_RANK):
    """
    Returns the target list of symbols to hold after rebalance.

    Logic:
      - Rank all stocks by momentum (rank 1 = best)
      - Enter: any stock with rank <= top_n
      - Stay:  currently held stocks with rank <= exit_rank
      - Exit:  currently held stocks with rank > exit_rank
    """
    mom_scores = compute_momentum_scores(prices)

    # Filter out illiquid / low-price stocks
    last_prices = prices.iloc[-1]
    eligible    = last_prices[last_prices >= config.MIN_STOCK_PRICE].index
    mom_scores  = mom_scores[mom_scores.index.isin(eligible)]

    # Rank: 1 = highest momentum
    ranks = mom_scores.rank(ascending=False, method='first')

    # Decision
    enter  = set(ranks[ranks <= top_n].index.tolist())
    stay   = set(s for s in current_holdings if s in ranks.index and ranks[s] <= exit_rank)
    target = list(enter | stay)

    # If over top_n, keep only best ranked
    if len(target) > top_n:
        target_ranks = ranks[ranks.index.isin(target)]
        target = target_ranks.nsmallest(top_n).index.tolist()

    # Log top picks
    top_display = ranks[ranks <= top_n].sort_values().head(10)
    logger.info(f"Top 10 by momentum rank:\n{top_display.to_string()}")
    logger.info(f"Target portfolio: {len(target)} stocks")

    return target, ranks


def compute_trade_list(current_holdings, target_portfolio,
                        current_prices, capital):
    """
    Given current holdings and target portfolio, compute:
      - stocks to BUY (new entries)
      - stocks to SELL (exits)
      - quantity for each BUY (equal weight)

    current_holdings: dict of {symbol: quantity}
    target_portfolio: list of symbols
    current_prices:   dict of {symbol: last_price}
    capital:          total capital to deploy

    Returns:
      buys:  list of (symbol, quantity)
      sells: list of (symbol, quantity)
    """
    current_symbols = set(current_holdings.keys())
    target_symbols  = set(target_portfolio)

    sells = [(s, current_holdings[s]) for s in current_symbols - target_symbols
             if current_holdings[s] > 0]
    new_entries = list(target_symbols - current_symbols)

    # Equal weight sizing
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
