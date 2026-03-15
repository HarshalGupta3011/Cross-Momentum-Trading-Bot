# Zerodha Cross-Sectional Momentum Bot

Live trading bot for the Nifty 500 Cross-Sectional Momentum Strategy with EMA 200 regime filter, built on Zerodha Kite Connect.

<img width="1920" height="1080" alt="Screenshot (669)" src="https://github.com/user-attachments/assets/4b3396c5-10c8-41b4-849f-6acaaa1a1dfb" />

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
2. Create a connect app(paid) → get your **API Key** and **API Secret**
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
2. **TOTP automation**: type your zerodha user id, password and totp secret in config.py

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
## AWS EC2 Deployment (for full automation)

Running the bot on AWS EC2 keeps it running 24/7 independently of your local machine — closing your laptop has no effect on the bot.

### 1. Launch an EC2 Instance
1. Go to [AWS Console](https://console.aws.amazon.com) → **EC2 → Launch Instance**
2. Configure:
   - **Name**: `momentum-bot`
   - **OS**: Ubuntu 24.04 LTS
   - **Instance type**: `t2.micro` (free tier eligible)
   - **Key pair**: Click **Create new key pair** → name it `momentum-key` → download the `.pem` file and save it safely
   - **Security group**: Allow SSH (port 22)
3. Click **Launch Instance**

### 2. Connect to Your Instance
```bash
# Mac / Linux
chmod 400 momentum-key.pem
ssh -i "momentum-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP

# Windows (PowerShell)
ssh -i "momentum-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```
> Find your public IP in EC2 dashboard → Instances → **Public IPv4 address**

### 3. Set Up the Server
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and tools
sudo apt install python3 python3-pip screen zip unzip -y

# Set timezone to IST (critical for scheduler)
sudo timedatectl set-timezone Asia/Kolkata
timedatectl   # verify it shows Asia/Kolkata
```

### 4. Upload Bot Files
```bash
# Run this on your LOCAL machine (not the VPS)
scp -i "momentum-key.pem" zerodha_momentum_bot.zip ubuntu@YOUR_EC2_PUBLIC_IP:~/
```

```bash
# Back on the VPS — extract files
cd ~
unzip zerodha_momentum_bot.zip
cd zerodha_momentum_bot
```

### 5. Install Dependencies
```bash
pip3 install -r requirements.txt --break-system-packages
```

### 6. Edit Config
```bash
nano config.py
# Fill in KITE_API_KEY, KITE_API_SECRET, TOTAL_CAPITAL
# Ctrl+X → Y → Enter to save
```

### 7. Test With Dry Run
```bash
python3 login.py                     # log in once to save token
python3 bot.py --dry-run --now       # verify everything works
```

### 8. Run as a Persistent Service (auto-restarts on crash/reboot)
```bash
sudo nano /etc/systemd/system/momentum_bot.service
```
Paste:
```ini
[Unit]
Description=Zerodha Momentum Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/zerodha_momentum_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```
Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable momentum_bot
sudo systemctl start momentum_bot
sudo systemctl status momentum_bot   # should show "active (running)"
```

### 9. Daily Login via Cron (8 AM IST)
```bash
crontab -e
```
Add:
```
0 8 * * 1-5 cd /home/ubuntu/zerodha_momentum_bot && python3 login.py >> logs/login.log 2>&1
```

### Useful Commands
```bash
# Check bot status
sudo systemctl status momentum_bot

# Watch live logs
tail -f ~/zerodha_momentum_bot/logs/bot.log

# Restart after config changes
sudo systemctl restart momentum_bot

# View order history
cat ~/zerodha_momentum_bot/logs/orders.csv
```

### AWS Cost
| Resource | Cost |
|---|---|
| t2.micro EC2 | Free for 12 months (750 hrs/month free tier) |
| After free tier | ~$8–10/month |

---
## Dashboard (Manual Control)
GUI for easy control
<img width="1920" height="1080" alt="Screenshot (669)" src="https://github.com/user-attachments/assets/4b3396c5-10c8-41b4-849f-6acaaa1a1dfb" />
<img width="1920" height="1080" alt="Screenshot (673)" src="https://github.com/user-attachments/assets/ae62eb2c-7c81-468a-b935-22b45492bde8" />



## Logs

All activity is logged to the `logs/` directory:

- **bot.log** — timestamped log of every action the bot takes
- **orders.csv** — record of every order with order_id, status, errors

- **portfolio.csv** — monthly portfolio snapshots (symbol, qty, price, value)

---
## Backtest 
Run the backtest.py file and edit the start and end date as your liking(make sure its not more than 4000 days limited by kiteconnect)
<img width="1972" height="1287" alt="equity_drawdown" src="https://github.com/user-attachments/assets/6ed7298b-c831-457d-bfb7-5c11072173b6" />

<img width="1657" height="657" alt="stats_table" src="https://github.com/user-attachments/assets/fc204d87-2675-454b-84d2-7725271002ba" />


## Disclaimer

This bot is for educational purposes. Live trading involves real financial risk. Always test thoroughly wth `--dry-run` before going live. Past backtest performance does not guarantee future results.
