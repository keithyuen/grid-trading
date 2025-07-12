# Grid Trading Bot with IBKR and `ib_async`

This project implements a grid trading bot using the Interactive Brokers API via [`ib_async`](https://github.com/ib-api-reloaded/ib_async). It supports a fully automated TQQQ-like strategy with configurable assets, persistent tracking, and a live Streamlit dashboard.

---

## ✅ Features
- Lot size & interval calculation based on historical drawdown logic
- GTC grid limit orders for consistent buy-low, sell-high execution
- Persistent SQLite tracking of trades, PnL, and open orders
- Live dashboard for monitoring performance and activity

---

## 🚀 Setup Instructions

### 1. Clone the Project
```bash
cd grid-trading
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🧠 IB Gateway Setup (Paper or Live)

### A. Download & Launch
- Download IB Gateway: https://www.interactivebrokers.com/en/index.php?f=16457
- Choose **Paper Trading** or **Live Trading**
- Log in with your IBKR credentials

### B. Configure API Access
Go to **Configure > Settings > API > Settings** and ensure:

- ✅ **Socket port: 4002** — this is your API port for **paper trading**  
  (Use **4001** for **live trading**)
- ✅ **Download open orders on connection**
- ✅ **Include market data in API log file**
- ✅ **Trusted IPs**: add `127.0.0.1`

---

## ⚙️ Configuration
Edit `config.yaml`:
```yaml
paper_trading: true
client_id: 1
# Use any number to identify this bot instance.
# Example: 1 for main bot, 2+ for other tools or dashboards
tws_port: 4002
strategy_budget: 50000
base_lot: 100
crash_pct: 0.87
range_fraction: 0.565
profit_pct: 0.015
symbol: "TQQQ"
```

> **Note on `client_id`:** This is not your IB account number. It is any integer you assign to identify this connection. Use different values if running multiple scripts or dashboards in parallel.

---

## 🧪 Run a Connection Test
To verify your IB Gateway/API setup before placing trades:
```bash
python test_connection.py
```
This will:
- Connect using `ib_async`
- Show current price for your symbol
- Print account summary details

---

## ▶️ Run the Bot
```bash
source venv/bin/activate #if not done yet
python main.py
```

The bot will:
- Place a market order if you don’t own any shares
- Ladder GTC buy orders downwards
- Sell each filled lot at +1.5% profit

---

## 📊 Launch Dashboard
```bash
streamlit run streamlit_dashboard.py
```

Dashboard includes:
- 🔁 Open Buy/Sell Orders
- ✅ Trade History
- 💰 Realized PnL summary

---

## 🔁 Restarting the Bot
The strategy is stateful:
- Reuses previous trade history
- Recalculates interval from `trade_logs.db`
- Ensures no duplicate trades or orders

## 📝 Logging
Logs are automatically managed with daily rotation:
- **Location**: `logs/` folder
- **Format**: `trading-YYYY-MM-DD.log`
- **Retention**: 30 days of logs
- **Rotation**: Automatic at midnight

Example log files:
```
logs/
├── trading-2025-07-10.log
├── trading-2025-07-11.log
└── trading-2025-07-12.log
```

---
# === OPTIONAL: Schedule restart daily and on crash ===
# PM2 is a process manager that can keep your Python script running,
# automatically restart on crash, and allow scheduled restarts with logging.
# Step 1: Install Node.js (if not already installed)
# This also installs npm, which is required for pm2
brew install node

# Step 2: Install PM2 globally using npm
npm install -g pm2

# === Start the Python app with PM2 ===
# Make sure to specify the full path to your virtual environment's Python
pm2 start /Users/keithyuen/python/grid-trading/main.py \
  --name gridtrader \
  --interpreter /Users/keithyuen/python/grid-trading/venv/bin/python

# === Schedule a daily restart at 9 PM Eastern Time (9 AM Singapore Time) ===
pm2 restart gridtrader --cron "0 9 * * *"

# === Save the PM2 process list for reboot persistence (optional) ===
pm2 save

# === View logs ===
pm2 logs gridtrader

# === Common PM2 Commands ===
pm2 list            # Show running processes
pm2 restart gridtrader
pm2 stop gridtrader
pm2 delete gridtrader
---

## 🛠️ Coming Soon (Optional Enhancements)
- Multi-symbol support with per-symbol configs
- Slack/email notifications
- Backtesting module

---

## 📄 License
MIT License

---

Feel free to fork and extend. Contributions welcome!