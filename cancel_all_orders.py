#!/usr/bin/env python3
"""
Script to cancel all existing open BUY and SELL orders from IBKR
"""

import yaml
from ibkr import IBKRClient
import time

def cancel_all_orders():
    """Cancel all open orders from IBKR"""
    
    print("🚫 Cancelling All Open Orders")
    print("=" * 40)
    
    # Load config
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        print("✅ Config loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # Initialize IBKR client with a unique client ID
    print("🔌 Initializing IBKR client...")
    ibkr = IBKRClient(
        paper=config.get('paper_trading', True),
        client_id=config['client_id'] + 10,  # Use a different client ID
        port=config['tws_port']
    )
    
    # Connect to IBKR
    print("🔗 Connecting to IBKR Gateway...")
    if not ibkr.connect():
        print("❌ Failed to connect to IBKR Gateway")
        return
    
    print("✅ Connected to IBKR Gateway")
    
    try:
        # Get the contract
        symbol = config['symbol']
        print(f"📈 Getting contract for {symbol}...")
        contract = ibkr.get_stock_contract(symbol)
        
        # Count open orders before cancellation
        print("\n📊 Checking current open orders...")
        open_buy_orders = ibkr.count_open_buy_orders(contract)
        open_sell_orders = ibkr.count_open_sell_orders(contract)
        
        print(f"   Open BUY orders: {open_buy_orders}")
        print(f"   Open SELL orders: {open_sell_orders}")
        
        if open_buy_orders == 0 and open_sell_orders == 0:
            print("✅ No open orders to cancel")
            return
        
        ibkr.cancel_all_orders(contract)
        ibkr.sleep(3)
        
        # Wait a moment for cancellations to process
        print("\n⏳ Waiting for cancellations to process...")
        time.sleep(3)
        
        # Verify cancellations
        print("\n🔍 Verifying cancellations...")
        remaining_buy_orders = ibkr.count_open_buy_orders(contract)
        remaining_sell_orders = ibkr.count_open_sell_orders(contract)
        
        print(f"   Remaining BUY orders: {remaining_buy_orders}")
        print(f"   Remaining SELL orders: {remaining_sell_orders}")
        
        if remaining_buy_orders == 0 and remaining_sell_orders == 0:
            print("✅ All orders successfully cancelled!")
        else:
            print("⚠️  Some orders may still be pending cancellation")
        
        # Also clear the database orders table
        print("\n🗄️  Clearing database order records...")
        try:
            import sqlite3
            conn = sqlite3.connect('trade_logs.db')
            conn.execute("DELETE FROM orders")
            conn.commit()
            conn.close()
            print("✅ Database orders cleared")
        except Exception as db_error:
            print(f"⚠️  Database error: {db_error}")
        
    except Exception as e:
        print(f"❌ Error during order cancellation: {e}")
    
    finally:
        # Disconnect
        print("\n🔌 Disconnecting from IBKR Gateway...")
        ibkr.disconnect()
        print("✅ Disconnected from IBKR Gateway")
    
    print("\n🎉 Order cancellation process completed!")

if __name__ == "__main__":
    cancel_all_orders() 