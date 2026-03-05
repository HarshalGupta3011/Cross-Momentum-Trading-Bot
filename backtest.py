"""
kite_backtest.py — Cross-Sectional Momentum Backtest using Kite Connect
=======================================================================
Single file, no TOTP, manual login only.

Usage:
    python kite_backtest.py
    python kite_backtest.py --clear-cache
    python kite_backtest.py --filter "EMA 200"

Requirements:
    pip install kiteconnect pandas numpy matplotlib
"""

import os
import sys
import json
import time
import logging
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
import requests
from datetime import datetime, date, timedelta
from kiteconnect import KiteConnect

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION — Edit this section before running
# ═══════════════════════════════════════════════════════════════

# Leave blank to auto-load from zerodha_momentum_bot/config.py
KITE_API_KEY    = ""
KITE_API_SECRET = ""
INITIAL_CAPITAL = 0   # set to 0 to auto-load from config.py

START_DATE      = "2021-01-01"
END_DATE        = "today"       # auto uses today's date

TOP_N           = 30
EXIT_RANK       = 34
MOMENTUM_WINDOW = 252
SKIP_DAYS       = 21
REBALANCE_FREQ  = "M"

REGIME_FILTERS  = {
    "No Filter" : None,
    "EMA 50"    : 50,
    "EMA 100"   : 100,
    "EMA 200"   : 200,
}



BROKERAGE_PCT   = 0.0003
STT_PCT         = 0.001
IMPACT_COST_PCT = 0.0005
TOTAL_COST_PCT  = BROKERAGE_PCT + STT_PCT + IMPACT_COST_PCT

NIFTY50_TOKEN   = 256265        # Standard Kite token for NIFTY 50 index
OUTPUT_DIR      = "backtest_results"
CACHE_DIR       = os.path.join(OUTPUT_DIR, "cache")

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR,  exist_ok=True)

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s | %(levelname)s | %(message)s",
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(OUTPUT_DIR, "backtest.log"))
    ]
)
logger = logging.getLogger(__name__)

# ── Auto-load credentials from bot config.py if not set above ──
if not KITE_API_KEY:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "zerodha_momentum_bot"))
        import config as _cfg
        KITE_API_KEY    = _cfg.KITE_API_KEY
        KITE_API_SECRET = _cfg.KITE_API_SECRET
        INITIAL_CAPITAL = _cfg.TOTAL_CAPITAL
        logger.info("✓ Loaded credentials from zerodha_momentum_bot/config.py")
    except Exception as e:
        logger.error(f"Could not load config.py: {e}")
        logger.error("Fill in KITE_API_KEY and KITE_API_SECRET at the top of this file.")
        sys.exit(1)

if INITIAL_CAPITAL == 0:
    INITIAL_CAPITAL = 1_000_000   # fallback default

ACCESS_TOKEN_FILE = "backtest_token.txt"

# ═══════════════════════════════════════════════════════════════
# STEP 1 — LOGIN
# ═══════════════════════════════════════════════════════════════

def get_kite() -> KiteConnect:
    """Login to Kite. Reuses today's token if available, else manual login."""
    kite = KiteConnect(api_key=KITE_API_KEY)

    # Try to reuse today's saved token
    try:
        with open(ACCESS_TOKEN_FILE) as f:
            data = json.load(f)
        if data.get("date") == str(date.today()):
            kite.set_access_token(data["access_token"])
            logger.info("✓ Reused saved access token")
            return kite
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Manual login
    print("\n" + "=" * 60)
    print("  ZERODHA LOGIN")
    print("=" * 60)
    print(f"\n1. Open this URL in your browser:\n\n   {kite.login_url()}\n")
    print("2. Log in with your Zerodha credentials.")
    print("3. You'll be redirected to a URL like:")
    print("   http://127.0.0.1?request_token=XXXXXXXX&status=success")
    print("4. Copy the request_token value.\n")

    request_token = input("Paste request_token here: ").strip()
    session       = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
    kite.set_access_token(session["access_token"])

    with open(ACCESS_TOKEN_FILE, "w") as f:
        json.dump({"date": str(date.today()),
                   "access_token": session["access_token"]}, f)

    logger.info("✓ Login successful")
    return kite


# ═══════════════════════════════════════════════════════════════
# STEP 2 — DOWNLOAD DATA FROM KITE
# ═══════════════════════════════════════════════════════════════

_instrument_cache = {}

def get_token(kite: KiteConnect, symbol: str) -> int | None:
    """Look up instrument token for a symbol."""
    global _instrument_cache

    cache_file = os.path.join(CACHE_DIR, "instruments.json")

    if not _instrument_cache:
        if os.path.exists(cache_file):
            mod_date = date.fromtimestamp(os.path.getmtime(cache_file))
            if mod_date == date.today():
                with open(cache_file) as f:
                    _instrument_cache = json.load(f)

        if not _instrument_cache:
            logger.info("Downloading NSE instruments list...")
            instruments = kite.instruments("NSE")
            _instrument_cache = {
                i["tradingsymbol"]: i["instrument_token"]
                for i in instruments
                if i["instrument_type"] == "EQ"
            }
            with open(cache_file, "w") as f:
                json.dump(_instrument_cache, f)
            logger.info(f"  ✓ {len(_instrument_cache)} instruments cached")

    return _instrument_cache.get(symbol)


def fetch_ohlcv(kite: KiteConnect, token: int, symbol: str,
                from_date: str, to_date: str) -> pd.DataFrame | None:
    """Fetch daily OHLCV. Cache = one file per symbol, reused every run."""

    # & in symbol names (e.g. M&M) breaks Windows filenames
    safe_sym   = symbol.replace("&", "-")
    cache_file = os.path.join(CACHE_DIR, f"{safe_sym}_{from_date}.csv")

    # ── Use cache if file exists, is non-empty, and readable ──
    if os.path.exists(cache_file) and os.path.getsize(cache_file) > 50:
        try:
            df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date")
            if len(df) > 0:
                return df          # ← cache hit, skip API call entirely
        except Exception:
            pass                   # corrupt file, fall through to re-download
        os.remove(cache_file)      # delete corrupt file

    # ── Download from Kite ──
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
        df = df.set_index("date")[["open", "high", "low", "close", "volume"]]
        df.to_csv(cache_file)
        return df

    except Exception as e:
        logger.warning(f"  Failed {symbol}: {e}")
        return None


def get_nifty500_universe() -> list:
    """
    Fetch the official Nifty 500 constituents list from NSE website.
    Falls back to cached CSV if download fails.
    Returns list of NSE trading symbols.
    """
    cache_file = os.path.join(CACHE_DIR, "nifty500_constituents.csv")

    # Use cached file if it was downloaded today
    if os.path.exists(cache_file):
        file_date = date.fromtimestamp(os.path.getmtime(cache_file))
        if file_date >= date.today():
            df = pd.read_csv(cache_file)
            symbols = df["Symbol"].str.strip().tolist()
            logger.info(f"  ✓ Nifty 500 loaded from cache: {len(symbols)} stocks")
            return symbols

    # Download from NSE
    url = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.nseindia.com/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        df.to_csv(cache_file, index=False)
        symbols = df["Symbol"].str.strip().tolist()
        logger.info(f"  ✓ Nifty 500 downloaded from NSE: {len(symbols)} stocks")
        return symbols

    except Exception as e:
        logger.warning(f"  NSE download failed ({e}), trying backup URL...")

    # Backup: NSE indices page
    backup_url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        resp = requests.get(backup_url, headers=headers, timeout=15)
        resp.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        df.to_csv(cache_file, index=False)
        symbols = df["Symbol"].str.strip().tolist()
        logger.info(f"  ✓ Nifty 500 downloaded from NSE backup: {len(symbols)} stocks")
        return symbols

    except Exception as e:
        logger.warning(f"  Backup also failed ({e})")

    # Last resort: use stale cache even if old
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file)
        symbols = df["Symbol"].str.strip().tolist()
        logger.warning(f"  Using stale cache: {len(symbols)} stocks")
        return symbols

    raise RuntimeError(
        "Could not fetch Nifty 500 list from NSE and no cache found.\n"
        "Download manually from: https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-500\n"
        "Save as: backtest_results/cache/nifty500_constituents.csv"
    )


def download_prices(kite: KiteConnect, universe: list, from_date: str, to_date: str) -> pd.DataFrame:
    """Download close prices for all universe symbols."""
    logger.info(f"Downloading price data for {len(universe)} symbols...")
    logger.info("(Cached files reused — only missing data fetched)")

    closes = {}
    for i, sym in enumerate(universe, 1):
        token = get_token(kite, sym)
        if not token:
            continue
        df = fetch_ohlcv(kite, token, sym, from_date, to_date)
        if df is not None and len(df) > 100:
            closes[sym] = df["close"]
        if i % 50 == 0:
            logger.info(f"  {i}/{len(universe)} done...")
        time.sleep(0.15)   # Kite rate limit ~3 req/sec

    prices = pd.DataFrame(closes).sort_index()
    prices = prices.dropna(axis=1, thresh=int(len(prices) * 0.8))
    prices = prices.ffill(limit=5)
    logger.info(f"✓ {prices.shape[1]} stocks × {len(prices)} days")
    return prices


def download_nifty50(kite: KiteConnect, from_date: str, to_date: str) -> pd.Series:
    """Download Nifty 50 index for regime filter."""
    logger.info("Downloading Nifty 50 index...")
    df = fetch_ohlcv(kite, NIFTY50_TOKEN, "NIFTY50_IDX", from_date, to_date)
    if df is None:
        raise ValueError("Could not fetch Nifty 50 data")
    logger.info(f"✓ Nifty 50: {len(df)} days")
    return df["close"].rename("NIFTY50")


# ═══════════════════════════════════════════════════════════════
# STEP 3 — SIGNALS & PORTFOLIO WEIGHTS
# ═══════════════════════════════════════════════════════════════

def compute_momentum(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.shift(SKIP_DAYS) / prices.shift(MOMENTUM_WINDOW + SKIP_DAYS) - 1


def compute_regime(nifty50: pd.Series, ema_window: int | None) -> pd.Series:
    if ema_window is None:
        return pd.Series(True, index=nifty50.index)
    ema = nifty50.ewm(span=ema_window, adjust=False).mean()
    return (nifty50 > ema).astype(bool)


def build_weights(prices: pd.DataFrame, nifty50: pd.Series,
                  ema_window: int | None) -> pd.DataFrame:
    """Monthly equal-weight allocation to top-N momentum stocks."""
    mom     = compute_momentum(prices)
    regime  = compute_regime(nifty50, ema_window)

    m_prices = prices.resample(REBALANCE_FREQ).last()
    m_mom    = mom.resample(REBALANCE_FREQ).last()
    m_regime = regime.resample(REBALANCE_FREQ).last()
    m_regime = m_regime.reindex(m_prices.index, method="ffill").fillna(False).astype(bool)
    m_ranks  = m_mom.rank(axis=1, ascending=False, method="first")

    holdings = pd.DataFrame(0.0, index=m_ranks.index, columns=m_ranks.columns)
    prev_held = set()

    for dt in m_ranks.index:
        ranks      = m_ranks.loc[dt]
        is_bullish = bool(m_regime.loc[dt])

        if not is_bullish:
            selected = set()
        else:
            enter    = set(ranks[ranks <= TOP_N].index.tolist())
            stay     = {s for s in prev_held
                        if s in ranks.index and ranks[s] <= EXIT_RANK}
            selected = enter | stay
            if len(selected) > TOP_N:
                sel_ranks = ranks[ranks.index.isin(selected)]
                selected  = set(sel_ranks.nsmallest(TOP_N).index.tolist())

        for s in selected:
            holdings.loc[dt, s] = 1.0
        prev_held = selected

    row_sums = holdings.sum(axis=1).replace(0, np.nan)
    return holdings.div(row_sums, axis=0).fillna(0.0)


# ═══════════════════════════════════════════════════════════════
# STEP 4 — SIMULATE PORTFOLIO
# ═══════════════════════════════════════════════════════════════

def simulate(prices: pd.DataFrame, weights: pd.DataFrame,
             label: str) -> dict:
    """Simulate daily portfolio value from monthly weights."""
    daily_w   = weights.reindex(prices.index, method="ffill").fillna(0.0)
    daily_ret = prices.pct_change().fillna(0.0)
    port_ret  = (daily_ret * daily_w).sum(axis=1)
    turnover  = daily_w.diff().abs().sum(axis=1)
    net_ret   = port_ret - turnover * TOTAL_COST_PCT
    equity    = (1 + net_ret).cumprod() * INITIAL_CAPITAL
    equity.name = label
    return {"label": label, "equity": equity, "returns": net_ret, "weights": weights}


# ═══════════════════════════════════════════════════════════════
# STEP 5 — PERFORMANCE METRICS
# ═══════════════════════════════════════════════════════════════

def calc_stats(result: dict) -> dict:
    equity  = result["equity"]
    returns = result["returns"]
    label   = result["label"]
    years   = len(returns) / 252

    total_ret    = (equity.iloc[-1] / INITIAL_CAPITAL - 1) * 100
    cagr         = ((equity.iloc[-1] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100
    ann_vol      = returns.std() * np.sqrt(252) * 100
    sharpe       = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
    down_std     = returns[returns < 0].std() * np.sqrt(252)
    sortino      = (returns.mean() * 252) / down_std if down_std > 0 else 0
    roll_max     = equity.cummax()
    dd_series    = (equity - roll_max) / roll_max * 100
    max_dd       = dd_series.min()
    calmar       = cagr / abs(max_dd) if max_dd != 0 else 0
    monthly_ret  = returns.resample("M").apply(lambda x: (1 + x).prod() - 1)
    win_rate     = (monthly_ret > 0).mean() * 100
    gp           = monthly_ret[monthly_ret > 0].sum()
    gl           = abs(monthly_ret[monthly_ret < 0].sum())
    pf           = gp / gl if gl > 0 else np.inf
    avg_hold     = (result["weights"] > 0).sum(axis=1).mean() if not result["weights"].empty else 0

    return {
        "Label"          : label,
        "Total Return"   : f"{total_ret:.2f}%",
        "CAGR"           : f"{cagr:.2f}%",
        "Ann. Volatility": f"{ann_vol:.2f}%",
        "Sharpe"         : f"{sharpe:.2f}",
        "Sortino"        : f"{sortino:.2f}",
        "Max Drawdown"   : f"{max_dd:.2f}%",
        "Calmar"         : f"{calmar:.2f}",
        "Win Rate"       : f"{win_rate:.1f}%",
        "Profit Factor"  : f"{pf:.2f}",
        "Final Value"    : f"Rs {equity.iloc[-1]/1e5:.1f}L",
        "Avg Holdings"   : f"{avg_hold:.1f}",
        "_cagr"          : cagr,
        "_max_dd"        : max_dd,
        "_sharpe"        : sharpe,
        "_dd_series"     : dd_series,
        "_monthly_ret"   : monthly_ret,
    }


# ═══════════════════════════════════════════════════════════════
# STEP 6 — CHARTS
# ═══════════════════════════════════════════════════════════════

DARK    = "#0d1117"
PANEL   = "#161b22"
GRID    = "#21262d"
TEXT    = "#e6edf3"
COLORS  = ["#00d4ff", "#00ff88", "#ffaa00", "#cc99ff"]


def plot_equity_and_drawdown(results: list, bench: dict):
    fig = plt.figure(figsize=(16, 10), facecolor=DARK)
    gs  = gridspec.GridSpec(2, 1, height_ratios=[2, 1], hspace=0.08)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    for ax in [ax1, ax2]:
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=TEXT, labelsize=9)
        ax.spines[:].set_color(GRID)
        ax.grid(alpha=0.3, color=GRID, linewidth=0.5)

    # Benchmark
    b_norm = bench["equity"] / INITIAL_CAPITAL * 100
    b_dd   = bench["stats"]["_dd_series"]
    ax1.plot(b_norm.index, b_norm.values, color="#ff4466",
             lw=1.5, ls="--", label="Nifty 50 B&H", zorder=2)
    ax2.fill_between(b_dd.index, b_dd.values, 0, color="#ff4466", alpha=0.2)
    ax2.plot(b_dd.index, b_dd.values, color="#ff4466", lw=1, ls="--")

    # Strategies
    for i, res in enumerate(results):
        c     = COLORS[i % len(COLORS)]
        s     = res["stats"]
        norm  = res["equity"] / INITIAL_CAPITAL * 100
        dd    = s["_dd_series"]
        label = f"{res['label']}  CAGR:{s['CAGR']}  DD:{s['Max Drawdown']}  Sharpe:{s['Sharpe']}"
        ax1.plot(norm.index, norm.values, color=c, lw=2, label=label, zorder=3)
        ax2.fill_between(dd.index, dd.values, 0, color=c, alpha=0.18)
        ax2.plot(dd.index, dd.values, color=c, lw=1)

    ax1.set_ylabel("Portfolio Value (% of initial)", color=TEXT, fontsize=10)
    ax1.set_title("Cross-Sectional Momentum — Equity Curves & Drawdown",
                  color=TEXT, fontsize=13, pad=10)
    ax1.legend(facecolor=PANEL, labelcolor=TEXT, fontsize=8,
               loc="upper left", framealpha=0.9)
    ax1.yaxis.label.set_color(TEXT)
    ax2.set_ylabel("Drawdown %", color=TEXT, fontsize=10)
    ax2.set_xlabel("Date",       color=TEXT, fontsize=10)
    ax2.yaxis.label.set_color(TEXT)
    ax2.xaxis.label.set_color(TEXT)
    plt.setp(ax1.get_xticklabels(), visible=False)

    path = os.path.join(OUTPUT_DIR, "equity_drawdown.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK)
    plt.close()
    logger.info(f"Saved: {path}")


def plot_stats_table(all_stats: list):
    metrics = [
        "Total Return", "CAGR", "Ann. Volatility", "Sharpe", "Sortino",
        "Max Drawdown", "Calmar", "Win Rate", "Profit Factor",
        "Final Value", "Avg Holdings",
    ]
    fig, ax = plt.subplots(figsize=(14, 5), facecolor=DARK)
    ax.set_facecolor(DARK)
    ax.axis("off")

    columns = ["Metric"] + [s["Label"] for s in all_stats]
    rows    = [[m] + [s.get(m, "-") for s in all_stats] for m in metrics]

    table = ax.table(cellText=rows, colLabels=columns,
                     cellLoc="center", loc="center", bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#1f3a5f")
            cell.set_text_props(color="#00d4ff", weight="bold")
        elif c == 0:
            cell.set_facecolor(PANEL)
            cell.set_text_props(color=TEXT, weight="bold")
        else:
            cell.set_facecolor(PANEL if r % 2 == 0 else "#1a1f27")
            cell.set_text_props(color=TEXT)
        cell.set_edgecolor(GRID)

    ax.set_title("Regime Filter Comparison — Performance Metrics",
                 color=TEXT, fontsize=12, pad=15)

    path = os.path.join(OUTPUT_DIR, "stats_table.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK)
    plt.close()
    logger.info(f"Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main(clear_cache: bool = False, only_filter: str = None):
    logger.info("=" * 65)
    logger.info("  KITE CROSS-SECTIONAL MOMENTUM BACKTEST")
    logger.info("=" * 65)

    end_date = date.today().strftime("%Y-%m-%d") if END_DATE.lower() == "today" else END_DATE

    if clear_cache:
        import shutil
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR, exist_ok=True)
        logger.info("Cache cleared.")

    # Login
    logger.info("\n[1/5] Logging in to Kite...")
    kite = get_kite()

    # Fetch Nifty 500 universe from NSE official CSV
    logger.info("Fetching Nifty 500 constituents from NSE...")
    universe = get_nifty500_universe()
    logger.info(f"Period  : {START_DATE} → {end_date}")
    logger.info(f"Universe: {len(universe)} stocks | Capital: Rs {INITIAL_CAPITAL:,}")

    # Download data
    logger.info("\n[2/5] Downloading data from Kite...")
    prices  = download_prices(kite, universe, START_DATE, end_date)
    nifty50 = download_nifty50(kite, START_DATE, end_date)
    nifty50 = nifty50.reindex(prices.index, method="ffill").dropna()

    # Build signals & simulate
    logger.info("\n[3/5] Running simulations...")

    filters = REGIME_FILTERS
    if only_filter:
        filters = {k: v for k, v in REGIME_FILTERS.items() if k == only_filter}
        if not filters:
            logger.error(f"Filter '{only_filter}' not found. Options: {list(REGIME_FILTERS.keys())}")
            sys.exit(1)

    results = []
    for label, ema_window in filters.items():
        logger.info(f"  {label}...")
        weights = build_weights(prices, nifty50, ema_window)
        result  = simulate(prices, weights, label)
        result["stats"] = calc_stats(result)
        results.append(result)

    # Benchmark
    logger.info("\n[4/5] Computing Nifty 50 benchmark...")
    bench_ret    = nifty50.pct_change().fillna(0)
    bench_equity = (1 + bench_ret).cumprod() * INITIAL_CAPITAL
    bench_equity.name = "Nifty 50 B&H"
    bench = {
        "label"  : "Nifty 50 B&H",
        "equity" : bench_equity,
        "returns": bench_ret,
        "weights": pd.DataFrame(),
    }
    bench["stats"] = calc_stats(bench)

    # Print summary
    logger.info("\n[5/5] Results")
    logger.info("=" * 65)
    show = ["CAGR","Sharpe","Sortino","Max Drawdown","Calmar","Win Rate","Final Value"]
    all_stats = [r["stats"] for r in results] + [bench["stats"]]
    header = f"{'Metric':<20}" + "".join(f"{s['Label']:>18}" for s in all_stats)
    logger.info(header)
    logger.info("-" * len(header))
    for m in show:
        row = f"{m:<20}" + "".join(f"{s.get(m,'-'):>18}" for s in all_stats)
        logger.info(row)

    # Charts
    logger.info("\nGenerating charts...")
    plot_equity_and_drawdown(results, bench)
    plot_stats_table(all_stats)

    logger.info(f"\n✅ Done! Charts saved to ./{OUTPUT_DIR}/")
    logger.info(f"   equity_drawdown.png")
    logger.info(f"   stats_table.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kite Momentum Backtest")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Delete cached data and re-download from Kite")
    parser.add_argument("--filter", type=str, default=None,
                        help='Run only one filter e.g. --filter "EMA 200"')
    args = parser.parse_args()
    main(clear_cache=args.clear_cache, only_filter=args.filter)
