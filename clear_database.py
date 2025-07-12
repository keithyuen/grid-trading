#!/usr/bin/env python3
"""
Script to clear all existing orders, PnL data, and trade history from the database
"""

import sqlite3
import os

def clear_database():
    """Clear all orders, PnL data, and trade history from the database"""
    
    db_path = 'trade_logs.db'
    
    if not os.path.exists(db_path):
        print("✅ Database file doesn't exist yet. Nothing to clear.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Count records before deletion
        orders_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        pnl_count = conn.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
        trades_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        positions_count = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
        latest_prices_count = conn.execute("SELECT COUNT(*) FROM latest_prices").fetchone()[0]
        
        # Clear orders table
        conn.execute("DELETE FROM orders")
        print(f"🗑️  Deleted {orders_count} orders")
        
        # Clear PnL table
        conn.execute("DELETE FROM pnl")
        print(f"🗑️  Deleted {pnl_count} PnL records")
        
        # Clear trades table
        conn.execute("DELETE FROM trades")
        print(f"🗑️  Deleted {trades_count} trades")
        
        # Clear positions table
        conn.execute("DELETE FROM positions")
        print(f"🗑️  Deleted {positions_count} positions")
        
        # Note: cancels table has been removed in favor of status-based tracking
        
        # Clear latest_prices table
        conn.execute("DELETE FROM latest_prices")
        print(f"🗑️  Deleted {latest_prices_count} latest prices")
        
        conn.commit()
        conn.close()
        
        print("✅ Database cleared successfully!")
        print("📊 Current database status:")
        
        # Show current database status
        conn = sqlite3.connect(db_path)
        trades_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        orders_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        pnl_count = conn.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
        positions_count = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
        latest_prices_count = conn.execute("SELECT COUNT(*) FROM latest_prices").fetchone()[0]
        conn.close()
        
        print(f"   Trades: {trades_count} records")
        print(f"   Orders: {orders_count} records")
        print(f"   PnL: {pnl_count} records")
        print(f"   Positions: {positions_count} records")
        print(f"   Latest Prices: {latest_prices_count} records")
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")

if __name__ == "__main__":
    print("🧹 Clearing Grid Trading Database (including trade history)")
    print("=" * 40)
    clear_database()
    print("\n🎉 Ready to test the updated trading bot!")
    print("Run 'python main.py' to start fresh.") 