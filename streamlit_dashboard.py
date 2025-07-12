# grid-trading/streamlit_dashboard.py

import streamlit as st
import sqlite3
import pandas as pd
import os
import yaml
from ibkr import IBKRClient
from utils import calculate_lot_size_and_interval
from database import TradeDB

DB_PATH = 'trade_logs.db'

st.set_page_config(layout="wide")
st.title("📈 Grid Trading Dashboard")

# Load config to get symbol
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
symbol = config['symbol']

db = TradeDB('trade_logs.db')

# Get current price and position for main symbol from DB
current_price = db.get_latest_price(symbol)
current_position = db.get_position(symbol)
position_value = current_position * current_price if current_price is not None and current_position is not None else None

st.markdown("## 📈 Current Position")
st.metric(label=f"{symbol} Position", value=f"{current_position} shares" if current_position is not None else "0 shares")
if position_value is not None:
    st.metric(label=f"{symbol} Position Value", value=f"${position_value:,.2f}")
else:
    st.metric(label=f"{symbol} Position Value", value="N/A")

# Show all positions in a table with current price and value
st.markdown("### All Positions")
all_positions = db.get_all_positions()
for pos in all_positions:
    sym = pos['symbol']
    qty = pos['position']
    price = db.get_latest_price(sym)
    pos['current_price'] = price
    pos['value'] = qty * price if price is not None else None
st.dataframe(all_positions)

def load_config():
    """Load configuration from YAML file"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Failed to load config: {e}")
        return None

def get_account_info():
    """Get account information from IBKR"""
    config = load_config()
    if not config:
        return None, None, None, None
    
    try:
        # Use a different client ID for the dashboard to avoid conflicts
        dashboard_client_id = config['client_id'] + 1  # Use next available client ID
        
        ibkr = IBKRClient(
            paper=config.get('paper_trading', True),
            client_id=dashboard_client_id,  # Use different client ID
            port=config['tws_port']
        )
        
        if ibkr.connect():
            ibkr.sleep(5)
            # Get account summary
            summary = ibkr.get_account_summary()
            
            # Extract cash information
            total_cash = 0
            available_funds = 0
            
            for item in summary:
                if item.tag == 'CashBalance' and item.currency == 'USD':
                    total_cash = float(item.value)
                elif item.tag == 'AvailableFunds' and item.currency == 'USD':
                    available_funds = float(item.value)
                elif item.tag == 'CashBalance' and item.currency == 'BASE':
                    total_cash_base = float(item.value)
                elif item.tag == 'AvailableFunds' and item.currency == 'BASE':
                    available_funds_base = float(item.value)
            
            ibkr.disconnect()
            return total_cash, available_funds, config, ibkr
        else:
            return None, None, config, None
    except Exception as e:
        st.error(f"Failed to connect to IBKR: {e}")
        return None, None, config, None

def create_tables_if_not_exist(conn):
    """Create database tables if they don't exist"""
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            action TEXT,
            price REAL,
            quantity INTEGER,
            timestamp TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            action TEXT,
            price REAL,
            quantity INTEGER,
            timestamp TEXT,
            order_id INTEGER,
            status TEXT DEFAULT 'Open'
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS pnl (
            symbol TEXT PRIMARY KEY,
            realized REAL
        )''')

@st.cache_data(ttl=30)
def load_data():
    # Check if database file exists, if not create it
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        create_tables_if_not_exist(conn)
        conn.close()
    
    conn = sqlite3.connect(DB_PATH)
    
    # Ensure tables exist
    create_tables_if_not_exist(conn)
    
    try:
        trades = pd.read_sql("SELECT * FROM trades ORDER BY timestamp DESC", conn)
    except:
        trades = pd.DataFrame(columns=['id', 'symbol', 'action', 'price', 'quantity', 'timestamp'])
    
    try:
        orders = pd.read_sql(
            """
            SELECT * FROM orders
            WHERE status = 'Open'
            ORDER BY timestamp DESC
            """, conn)
    except:
        orders = pd.DataFrame(columns=['id', 'symbol', 'action', 'price', 'quantity', 'timestamp', 'order_id', 'status'])
    
    try:
        pnl = pd.read_sql("SELECT * FROM pnl", conn)
    except:
        pnl = pd.DataFrame(columns=['symbol', 'realized'])
    
    conn.close()
    return trades, orders, pnl

# Load data
trades, orders, pnl = load_data()

# Get account information
total_cash, available_funds, config, ibkr = get_account_info()

# Display account information
st.markdown("---")
st.subheader("💰 Account Information")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if total_cash is not None:
        st.metric("Total Cash", f"${total_cash:,.2f}")
    else:
        st.metric("Total Cash", "N/A")

with col2:
    if available_funds is not None:
        st.metric("Available Funds", f"${available_funds:,.2f}")
    else:
        st.metric("Available Funds", "N/A")

with col3:
    if config:
        strategy_budget = config.get('strategy_budget', 0)
        st.metric("Strategy Budget", f"${strategy_budget:,.2f}")
    else:
        st.metric("Strategy Budget", "N/A")

with col4:
    if config and not trades.empty:
        # Calculate available cash for strategy
        db = sqlite3.connect(DB_PATH)
        used_cash = db.execute('SELECT SUM(price * quantity) FROM orders WHERE action = "BUY" AND status = "Open"', ()).fetchone()[0] or 0
        realized_pnl = db.execute('SELECT SUM(realized) FROM pnl', ()).fetchone()[0] or 0
        db.close()
        
        available_cash = strategy_budget + realized_pnl - used_cash
        st.metric("Available for Strategy", f"${available_cash:,.2f}")
    else:
        st.metric("Available for Strategy", "N/A")

# Display current market information if available
if config and ibkr:
    try:
        symbol = config['symbol']
        contract = ibkr.get_stock_contract(symbol)
        current_price = ibkr.get_market_price(contract)
        
        st.markdown("---")
        st.subheader("📊 Market Information")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(f"Current {symbol} Price", f"${current_price:.2f}")
        
        with col2:
            if config and not trades.empty:
                # Calculate lot size and interval
                db = sqlite3.connect(DB_PATH)
                used_cash = db.execute('SELECT SUM(price * quantity) FROM orders WHERE action = "BUY" AND status = "Open"', ()).fetchone()[0] or 0
                realized_pnl = db.execute('SELECT SUM(realized) FROM pnl', ()).fetchone()[0] or 0
                db.close()
                
                available_cash = strategy_budget + realized_pnl - used_cash
                lot_size, interval = calculate_lot_size_and_interval(
                    available_cash, 
                    current_price,
                    crash_pct=config['crash_pct'],
                    range_fraction=config['range_fraction']
                )
                st.metric("Calculated Lot Size", f"{lot_size} shares")
        
        with col3:
            if 'interval' in locals():
                st.metric("Grid Interval", f"${interval:.2f}")
        
    except Exception as e:
        st.warning(f"Could not load market information: {e}")

# Display database status
if trades.empty and orders.empty:
    st.info("📊 No trading data yet. Start the trading bot to see activity here!")
    st.stop()

st.markdown("---")
st.subheader("📈 Trading Activity")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🔁 Open Buy Orders")
    buy_orders = orders[orders['action'] == 'BUY']
    if not buy_orders.empty:
        st.dataframe(buy_orders)
    else:
        st.info("No open buy orders")

with col2:
    st.subheader("📤 Open Sell Orders")
    sell_orders = orders[orders['action'] == 'SELL']
    if not sell_orders.empty:
        st.dataframe(sell_orders)
    else:
        st.info("No open sell orders")

st.subheader("✅ Trade History")
if not trades.empty:
    st.dataframe(trades)
else:
    st.info("No trade history yet")

# --- Order History Section ---
st.subheader("📜 Order History")
if not orders.empty:
    # Load all orders (not just open) from the database
    conn = sqlite3.connect(DB_PATH)
    all_orders_df = pd.read_sql("SELECT * FROM orders ORDER BY timestamp DESC", conn)
    conn.close()
    # Show relevant columns
    columns_to_show = ['symbol', 'action', 'price', 'quantity', 'timestamp', 'order_id', 'status']
    st.dataframe(all_orders_df[columns_to_show])
else:
    st.info("No order history yet")

st.subheader("💰 Realized PnL")
if not pnl.empty:
    st.dataframe(pnl)
    total_pnl = pnl['realized'].sum()
    st.metric("Total Realized PnL", f"${total_pnl:,.2f}")
else:
    st.info("No PnL data yet")

# Add some helpful information
st.markdown("---")
st.markdown("### 📋 How to Use")
st.markdown("""
1. **Start the trading bot**: `python main.py`
2. **Monitor activity**: This dashboard will update automatically
3. **View trades**: See all executed trades in the Trade History section
4. **Track orders**: Monitor open buy and sell orders
5. **Check PnL**: View realized profits and losses
6. **Account info**: Monitor your account cash and strategy budget
""")