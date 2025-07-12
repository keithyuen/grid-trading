#!/usr/bin/env python3
"""
Test script to verify dashboard database functionality
"""

import sqlite3
import pandas as pd
from database import TradeDB

def test_dashboard_database():
    """Test that the dashboard can properly access the database"""
    
    print("🧪 Testing Dashboard Database Functionality")
    print("=" * 50)
    
    # Test with the main database file
    db_path = 'trade_logs.db'
    
    try:
        # Initialize database
        db = TradeDB(db_path)
        print("✅ Database initialized successfully")
        
        # Add some test data
        print("\n📝 Adding test data...")
        db.record_trade('TQQQ', 'BUY', 84.20, 14)
        db.record_trade('TQQQ', 'SELL', 85.46, 14)
        db.record_order('TQQQ', 'BUY', 83.21, 14)
        db.record_order('TQQQ', 'SELL', 85.29, 14)
        db.record_realized_pnl('TQQQ', 85.46, 14)
        
        print("✅ Test data added successfully")
        
        # Test reading data directly
        print("\n📊 Testing data retrieval...")
        conn = sqlite3.connect(db_path)
        
        # Test trades table
        trades = pd.read_sql("SELECT * FROM trades ORDER BY timestamp DESC", conn)
        print(f"✅ Trades table: {len(trades)} records")
        if not trades.empty:
            print(f"   Latest trade: {trades.iloc[0]['action']} {trades.iloc[0]['quantity']} shares at ${trades.iloc[0]['price']:.2f}")
        
        # Test orders table
        orders = pd.read_sql("SELECT * FROM orders ORDER BY timestamp DESC", conn)
        print(f"✅ Orders table: {len(orders)} records")
        if not orders.empty:
            print(f"   Latest order: {orders.iloc[0]['action']} {orders.iloc[0]['quantity']} shares at ${orders.iloc[0]['price']:.2f}")
        
        # Test pnl table
        pnl = pd.read_sql("SELECT * FROM pnl", conn)
        print(f"✅ PnL table: {len(pnl)} records")
        if not pnl.empty:
            total_pnl = pnl['realized'].sum()
            print(f"   Total realized PnL: ${total_pnl:.2f}")
        
        conn.close()
        
        # Test database methods
        print("\n🔧 Testing database methods...")
        committed_cash = db.get_committed_cash('TQQQ')
        realized_pnl = db.get_realized_pnl('TQQQ')
        print(f"✅ Committed cash: ${committed_cash:.2f}")
        print(f"✅ Realized PnL: ${realized_pnl:.2f}")
        
        # Test order history
        open_orders = db.get_open_orders()
        print(f"✅ Open orders: {len(open_orders)} records")
        
        # Test trade history
        trade_history = db.get_trade_history('TQQQ')
        print(f"✅ Trade history: {len(trade_history)} records")
        
        print("\n🎉 Dashboard database test passed!")
        print("\n📋 You can now:")
        print("1. Run 'streamlit run streamlit_dashboard.py' to view the dashboard")
        print("2. Run 'python main.py' to start trading")
        print("3. The dashboard will show the test data and any new trading activity")
        
    except Exception as e:
        print(f"❌ Dashboard database test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dashboard_database() 