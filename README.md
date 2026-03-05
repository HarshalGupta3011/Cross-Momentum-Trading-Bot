# Zerodha Cross-Sectional Momentum Bot

Live trading bot for the Nifty 500 Cross-Sectional Momentum Strategy with EMA 200 regime filter, built on Zerodha Kite Connect.

---

## Strategy Summary

| Parameter | Value |
|---|---|
| Universe | Nifty 500 (100+ liquid NSE stocks) |
| Signal | 12-1 month momentum |
| Selection | Top 30 stocks by momentum rank |
| Exit rule | Exit if rank drops below 34 |
| Rebalance | Monthly (last trading day) |
| Regime filter | Nifty 50 > EMA 200 → invest; below → cash |
| Order type | Market orders, CNC (delivery) |
| Position sizing | Equal weight |

---

## File Structure

```
zerodha_momentum_bot/
├── bot.py            ← Main entry point / scheduler
├── config.py         ← All settings (edit this first!)
├── login.py          ← Kite Connect auth & token management
├── signals.py        ← Momentum scores + regime filter logic
├── orders.py         ← Order placement + portfolio tracking
├── alerts.py         ← Telegram notifications
├── requirements.txt
└── logs/
    ├── bot.log       ← Full activity log
    ├── orders.csv    ← Every order placed
    └── portfolio.csv ← Monthly portfolio snapshots
```

---

## Setup Instructions

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Zerodha Kite API access
1. Go to [https://developers.kite.trade/](https://developers.kite.trade/)
2. Create an app → get your **API Key** and **API Secret**
3. Set redirect URL to `http://127.0.0.1` in your app settings

### 3. Edit config.py
```python
KITE_API_KEY    = "your_api_key"
KITE_API_SECRET = "your_api_secret"
TOTAL_CAPITAL   = 1_000_000   # Your trading capital in Rs
```

### 4. (Optional) Set up Telegram alerts
1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Get your chat ID via [@userinfobot](https://t.me/userinfobot)
3. Fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in config.py

---

## Running the Bot

### First-time login (run this manually each morning, or automate)
```bash
python login.py
```
This opens the Zerodha login URL in your browser. After logging in, paste the `request_token` from the redirect URL. The access token is saved and reused for the rest of the day.

### Dry run (test without placing real orders)
```bash
python bot.py --dry-run --now
```
This forces an immediate rebalance simulation — perfect for testing your setup.

### Force a real rebalance right now
```bash
python bot.py --now
```

### Start the live scheduler (runs daily at 9:30 AM IST)
```bash
python bot.py
```
Keep this running as a background process. On the last trading day of each month at 9:30 AM, it will execute the rebalance automatically.

---

## Running as a Background Service (Linux/Mac)

```bash
# Using nohup
nohup python bot.py > logs/nohup.out 2>&1 &

# Or using screen
screen -S momentum_bot
python bot.py
# Ctrl+A then D to detach
```

### Windows Task Scheduler
Create a task that runs `python bot.py --now` on a monthly schedule.

---

## Daily Login Automation (Optional)

Zerodha access tokens expire daily at midnight. For fully automated running, you need a way to refresh the token daily. Options:

1. **Manual**: Run `python login.py` each morning before market open
2. **TOTP automation**: Use `pyotp` with your Zerodha TOTP secret to automate the login flow (requires some extra setup — see Kite Connect docs)

---

## Risk Management

The bot has built-in safeguards:

| Safeguard | Default | Description |
|---|---|---|
| Regime filter | EMA 200 | Goes to cash if Nifty 50 < EMA 200 |
| Kill switch | 20% drawdown | Halts all trading if portfolio drops 20% from peak |
| Max position | 5% | No single stock can exceed 5% of capital |
| Min price | Rs 50 | Skips illiquid penny stocks |
| Market hours guard | 9:15–15:30 | Won't place orders outside NSE hours |

---

## Logs

All activity is logged to the `logs/` directory:

- **bot.log** — timestamped log of every action the bot takes
- **orders.csv** — record of every order with order_id, status, errors
- **portfolio.csv** — monthly portfolio snapshots (symbol, qty, price, value)

---

## Disclaimer

This bot is for educational purposes. Live trading involves real financial risk. Always test thoroughly with `--dry-run` before going live. Past backtest performance does not guarantee future results.
