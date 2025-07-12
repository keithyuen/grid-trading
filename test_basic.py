#!/usr/bin/env python3
"""
Basic test script to verify the grid trading bot functionality
"""

import yaml
from ibkr import IBKRClient
from utils import calculate_lot_size_and_interval
from database import TradeDB

def test_basic_functionality():
    """Test basic functionality without placing actual orders"""
    
    print("🧪 Testing Grid Trading Bot Basic Functionality")
    print("=" * 50)
    
    # Load config
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        print("✅ Config loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # Test IBKR connection
    print("\n🔌 Testing IBKR Connection...")
    ibkr = IBKRClient(
        paper=config.get('paper_trading', True),
        client_id=config['client_id'],
        port=config['tws_port']
    )
    
    if ibkr.connect():
        print("✅ Connected to IBKR Gateway")
        
        # Test getting contract
        try:
            contract = ibkr.get_stock_contract(config['symbol'])
            print(f"✅ Created contract for {config['symbol']}")
        except Exception as e:
            print(f"❌ Failed to create contract: {e}")
            ibkr.disconnect()
            return
        
        # Test getting market price
        try:
            current_price = ibkr.get_market_price(contract)
            print(f"✅ Current {config['symbol']} price: ${current_price:.2f}")
        except Exception as e:
            print(f"❌ Failed to get market price: {e}")
            ibkr.disconnect()
            return
        
        # Test position checking
        try:
            has_position = ibkr.has_position(config['symbol'])
            position = ibkr.get_position(config['symbol'])
            print(f"✅ Position check: {has_position}, Size: {position}")
        except Exception as e:
            print(f"❌ Failed to check position: {e}")
        
        # Test account summary
        try:
            summary = ibkr.get_account_summary()
            print(f"✅ Account summary retrieved ({len(summary)} items)")
        except Exception as e:
            print(f"❌ Failed to get account summary: {e}")
        
        ibkr.disconnect()
        print("✅ Disconnected from IBKR Gateway")
    else:
        print("❌ Failed to connect to IBKR Gateway")
        return
    
    # Test database functionality
    print("\n💾 Testing Database Functionality...")
    try:
        db = TradeDB('test_trade_logs.db')
        print("✅ Database initialized")
        
        # Test basic database operations
        db.record_trade('TEST', 'BUY', 100.0, 10)
        db.record_order('TEST', 'BUY', 99.0, 10)
        
        committed_cash = db.get_committed_cash('TEST')
        realized_pnl = db.get_realized_pnl('TEST')
        
        print(f"✅ Database operations: Committed cash: ${committed_cash:.2f}, PnL: ${realized_pnl:.2f}")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return
    
    # Test calculation function with current market price
    print("\n🧮 Testing Calculation Function with Current Market Price...")
    try:
        test_cash = 50000
        
        # Use the actual current price we got from IBKR
        if 'current_price' in locals() and current_price and current_price > 0:
            test_price = current_price
        else:
            # Fallback to a reasonable price if we couldn't get current price
            test_price = 84.2  # Approximate TQQQ price
        
        lot_size, interval = calculate_lot_size_and_interval(
            test_cash, 
            test_price,
            crash_pct=config['crash_pct'],
            range_fraction=config['range_fraction']
        )
        
        print(f"✅ Calculation test with current market price:")
        print(f"   Cash: ${test_cash:,.2f}")
        print(f"   Current {config['symbol']} Price: ${test_price:.2f}")
        print(f"   Lot Size: {lot_size} shares")
        print(f"   Interval: ${interval:.2f}")
        
        # Calculate how many intervals we can place
        intervals_possible = int(test_cash / (lot_size * config['range_fraction'] * test_price))
        print(f"   Intervals possible: {intervals_possible}")
        
        # Show what the grid would look like
        print(f"\n📊 Sample Grid Orders (first 5 levels):")
        for i in range(1, min(6, intervals_possible + 1)):
            buy_price = test_price - (interval * i)
            order_cost = buy_price * lot_size
            print(f"   Level {i}: Buy {lot_size} shares at ${buy_price:.2f} (Cost: ${order_cost:.2f})")
        
    except Exception as e:
        print(f"❌ Calculation test failed: {e}")
        return
    
    print("\n🎉 All basic tests passed!")
    print("\n📋 Next steps:")
    print("1. Run 'python test_connection.py' to verify IBKR connection")
    print("2. Run 'python main.py' to start the trading bot")
    print("3. Run 'streamlit run streamlit_dashboard.py' to view dashboard")

if __name__ == "__main__":
    test_basic_functionality() 