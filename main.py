# grid-trading/main.py

import logging
import time
import yaml
from utils import setup_daily_logging, calculate_lot_size_and_interval, round_price
from ibkr import IBKRClient
from database import TradeDB
import sqlite3

# --- GLOBAL LOGGING CONFIGURATION ---
logger = setup_daily_logging(log_folder='logs', log_level=logging.INFO)

CONFIG_FILE = 'config.yaml'

def load_config():
    """Load configuration from YAML file"""
    with open(CONFIG_FILE, 'r') as f:
        return yaml.safe_load(f)

def main():
    # Load configuration
    config = load_config()
    
    logger.info("Starting Grid Trading Bot")
    print("🚀 Starting Grid Trading Bot...")  # Direct print for immediate feedback
    
    # Initialize database
    db = TradeDB('trade_logs.db')
    print("📊 Database initialized")

    # --- TESTING ONLY: Clear DB, cancel all orders, close all positions ---
    # Uncomment the following lines for a clean test run
    # from cancel_all_orders import cancel_all_orders
    # from close_position import close_position
    # db.clear_all()  # Make sure TradeDB has a clear_all() method
    # cancel_all_orders()
    # close_position()
    # time.sleep(15)
    # ---------------------------------------------------------------
    
    # Initialize IBKR client
    print("🔌 Initializing IBKR client...")
    ibkr = IBKRClient(
        paper=config.get('paper_trading', True),
        client_id=config['client_id'],
        port=config['tws_port']
    )
    
    # Connect to IBKR
    print("🔗 Connecting to IBKR Gateway...")
    if not ibkr.connect():
        logger.error("Failed to connect to IBKR Gateway")
        print("❌ Failed to connect to IBKR Gateway")
        return
    
    print("✅ Connected to IBKR Gateway")

    # Sync open orders from IBKR to repopulate in-memory tracking
    ibkr.sync_open_orders_from_ibkr()
    ibkr.update_position(config['symbol'])
    
    try:
        symbol = config['symbol']
        print(f"📈 Getting contract for {symbol}...")
        contract = ibkr.get_stock_contract(symbol)
        
        # Get current market price
        print("💰 Getting current market price...")
        try:
            current_price = ibkr.get_market_price(contract)
            logger.info(f"Current {symbol} price: ${current_price}")
            print(f"💰 Current {symbol} price: ${current_price}")
        except Exception as e:
            logger.error(f"Failed to get market price: {e}")
            print(f"❌ Failed to get market price: {e}")
            logger.info("Market may be closed. Using last known price from database or config fallback.")
            
            # Try to get last known price from database
            try:
                conn = sqlite3.connect('trade_logs.db')
                last_trade = conn.execute(
                    "SELECT price FROM trades WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1", 
                    (symbol,)
                ).fetchone()
                conn.close()
                
                if last_trade:
                    current_price = last_trade[0]
                    logger.info(f"Using last known price from database: ${current_price}")
                    print(f"📊 Using last known price from database: ${current_price}")
                else:
                    # Use fallback price from config
                    current_price = config.get('fallback_price', 80.00)
                    logger.info(f"Using fallback price from config: ${current_price}")
                    print(f"📊 Using fallback price from config: ${current_price}")
            except Exception as db_error:
                logger.error(f"Database error: {db_error}")
                current_price = config.get('fallback_price', 80.00)  # Fallback price from config
                logger.info(f"Using fallback price from config: ${current_price}")
                print(f"📊 Using fallback price from config: ${current_price}")
        
        # Calculate available cash (budget + realized PnL - committed cash)
        print("💵 Calculating available cash...")
        total_budget = config['strategy_budget']
        used_cash = db.get_committed_cash(symbol)
        realized_pnl = db.get_realized_pnl(symbol)
        available_cash = total_budget + realized_pnl - used_cash

        # Store the latest price in the database for dashboard use
        db.set_latest_price(symbol, current_price)
        
        # Debug logging
        logger.info(f"Total budget: ${total_budget}")
        logger.info(f"Used cash: ${used_cash}")
        logger.info(f"Realized PnL: ${realized_pnl}")
        logger.info(f"Available cash: ${available_cash}")
        logger.info(f"Current price: ${current_price}")
        logger.info(f"Crash pct: {config['crash_pct']}")
        logger.info(f"Range fraction: {config['range_fraction']}")
        
        # Validate inputs before calculation
        if available_cash <= 0:
            logger.error(f"Available cash is not positive: ${available_cash}")
            return
        
        if current_price <= 0 or not current_price:
            logger.error(f"Current price is not valid: {current_price}")
            return
        
        # Calculate lot size and interval based on trading plan
        try:
            lot_size, interval = calculate_lot_size_and_interval(
                available_cash, 
                current_price,
                crash_pct=config['crash_pct'],
                range_fraction=config['range_fraction']
            )
            
            logger.info(f"Calculated lot size: {lot_size} shares")
            logger.info(f"Calculated interval: ${interval:.2f}")
            
        except Exception as e:
            logger.error(f"Calculation failed: {e}")
            logger.error(f"Inputs - Available cash: ${available_cash}, Current price: ${current_price}")
            return
        
        # Main trading loop
        logger.info("Entering main trading loop...")
        while True:
            try:
                # 1. Log current market price
                try:
                    current_price = ibkr.get_market_price(contract)
                    logger.info(f"Current market price: ${current_price}")
                    # Store the latest price in the database for dashboard use
                    db.set_latest_price(symbol, current_price)
                except Exception as price_error:
                    logger.error(f"Failed to get market price: {price_error}")
                    # Use fallback price from database or config
                    fallback_price = db.get_latest_price(symbol)
                    if fallback_price:
                        current_price = fallback_price
                        logger.info(f"Using fallback price from database: ${current_price}")
                    else:
                        current_price = config.get('fallback_price', 80.00)  # Fallback price from config
                        logger.info(f"Using fallback price from config: ${current_price}")

                # Recalculate available cash, lot size, and interval dynamically
                used_cash = db.get_committed_cash(symbol)
                realized_pnl = db.get_realized_pnl(symbol)
                available_cash = total_budget + realized_pnl - used_cash
                lot_size, interval = calculate_lot_size_and_interval(
                    available_cash, 
                    current_price,
                    crash_pct=config['crash_pct'],
                    range_fraction=config['range_fraction']
                )
                # guardrail to prevent negative cash
                if available_cash < 2000:
                    logger.warning(f"Available cash (${available_cash:.2f}) is low. No new orders will be placed.")
                    time.sleep(120)
                    continue  # Skip to next loop iteration

                # 2. Check current position and open orders
                try:
                    has_position = ibkr.has_position(symbol)
                    current_position = ibkr.get_position(symbol)
                    open_buy_orders = ibkr.count_open_buy_orders(contract)
                    open_sell_orders = ibkr.count_open_sell_orders(contract)
                    
                    logger.info(f"Current position: {current_position} shares, Open buy orders: {open_buy_orders}, Open sell orders: {open_sell_orders}")
                    logger.info(f"IBKR placed total orders: {len(ibkr.open_orders)} orders")
                except Exception as status_error:
                    logger.error(f"Failed to get position/order status: {status_error}")
                    ibkr.sleep(10)
                    continue

                # 3. Entry condition: no position
                if current_position == 0:
                    # Check if market is open before placing orders
                    trading_period = ibkr.get_trading_period()
                    if trading_period == 'closed':
                        logger.warning("Market is closed. Skipping order placement.")
                        ibkr.sleep(30) # Wait 30 seconds before checking again
                        continue
                    
                    logger.info("No position. Placing market bracket order...")
                    
                    # Place initial market bracket order (market buy + attached limit sell)
                    trades = ibkr.place_market_bracket_order(contract, lot_size, profit_pct=config['profit_pct'])
                    logger.info(f"[ORDER] Placed market bracket order for {lot_size} shares with {config['profit_pct']*100:.1f}% profit target")
                    
                    # Wait for the market order to be processed
                    ibkr.sleep(30)
                    continue

                # 4. Place grid bracket orders if no open buy orders - starting up or possibly price drops and filled all orders
                if open_buy_orders == 0:
                    # Check if market is open before placing orders
                    trading_period = ibkr.get_trading_period()
                    if trading_period == 'closed':
                        logger.warning("Market is closed. Skipping grid order placement.")
                        ibkr.sleep(30)  # Wait 30 seconds before checking again
                        continue
                    
                    logger.info("No open buy orders. Placing grid bracket orders...")
                    num_orders = 5
                    for i in range(1, num_orders + 1):
                        buy_price = round_price(current_price - (interval * i))
                        trades = ibkr.place_bracket_order(contract, lot_size, buy_price, profit_pct=config['profit_pct'])
                        logger.info(f"[ORDER] Placed grid bracket order {i} at ${buy_price:.2f} for {lot_size} shares with {config['profit_pct']*100:.1f}% profit target")
                        ibkr.sleep(2)  # Small delay between orders
                    
                    # Wait for grid orders to be processed
                    logger.info("Waiting for grid bracket orders to be processed by IBKR...")
                    time.sleep(30)
                    
                    # Verify grid orders were placed
                    open_buy_orders_after = ibkr.count_open_buy_orders(contract)
                    logger.info(f"After placing grid bracket orders, open buy orders: {open_buy_orders_after}")
                    
                    if open_buy_orders_after == 0:
                        logger.warning("Grid bracket orders were placed but not detected by IBKR. This may indicate an issue.")
                    
                    continue

                # 5. Check for any fills and process them
                fills = ibkr.check_filled_orders()
                
                for fill in fills:
                    logger.info(f"[TRADE] Order filled: {fill['action']} {fill['quantity']} shares at ${fill['price']:.2f}")
                    
                    if fill['action'] == 'BUY':
                        # Buy order filled - the attached sell order is already in place via bracket order
                        logger.info(f"Buy order filled. Attached sell order is already active with {config['profit_pct']*100:.1f}% profit target")
                    
                    elif fill['action'] == 'SELL':
                        # Sell order filled - record realized PnL
                        db.record_realized_pnl(symbol, fill['price'], fill['quantity'])
                        logger.info(f"Realized profit from sell order: ${fill['price']:.2f} x {fill['quantity']} shares")
                
                # Sync open orders from IBKR to repopulate in-memory tracking
                ibkr.sleep(5)
                ibkr.sync_open_orders_from_ibkr()
                #ibkr.sleep(2)
                # update position
                ibkr.update_position(symbol)
                
                # Sleep before next check
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal. Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    finally:
        # Cleanup
        logger.info("Disconnecting from IBKR Gateway")
        ibkr.disconnect()

if __name__ == "__main__":
    main()