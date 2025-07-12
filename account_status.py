#!/usr/bin/env python3
"""
Show available cash, all current positions, open orders, and trade fills for the last 24 hours.
"""

import yaml
from ibkr import IBKRClient
import sqlite3
from datetime import datetime, timedelta


def show_account_status():
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Connect to IBKR
    ibkr = IBKRClient(
        paper=config.get('paper_trading', True),
        client_id=config['client_id'] + 50,  # Unique client ID
        port=config['tws_port']
    )
    if not ibkr.connect():
        print("❌ Failed to connect to IBKR Gateway")
        return

    try:
        print("\n💰 Available Cash:")
        summary = ibkr.get_account_summary()
        cash = None
        for item in summary:
            tag = getattr(item, 'tag', None) or item.get('tag')
            value = getattr(item, 'value', None) or item.get('value')
            if tag in ('TotalCashBalance', 'CashBalance', 'AvailableFunds'):
                cash = value
                break
        if cash is not None:
            print(f"  {cash}")
        else:
            print("  (Could not determine cash balance)")

        print("\n📊 Current Positions:")
        positions = ibkr.ib.positions()
        positions = list(positions) if positions else []
        if not positions:
            print("  (No open positions)")
        else:
            for pos in positions:
                symbol = pos.contract.symbol
                qty = pos.position
                avg_price = getattr(pos, 'avgCost', 'N/A')
                print(f"  {symbol}: {qty} shares @ {avg_price}")

        print("\n📋 Open Orders:")
        open_orders = ibkr.get_open_orders()
        if not open_orders:
            print("  (No open orders)")
        else:
            for order in open_orders:
                symbol = order.get('symbol')
                action = order.get('action')
                qty = order.get('quantity')
                price = order.get('price', 'MKT')
                status = order.get('status', 'Unknown')
                print(f"  {symbol}: {action} {qty} @ {price} ({status})")

        print("\n🕒 Trade Fills (Last 24 Hours):")
        # Query fills from trade_logs.db
        try:
            conn = sqlite3.connect('trade_logs.db')
            c = conn.cursor()
            since = (datetime.utcnow() - timedelta(days=1)).isoformat()
            c.execute("""
                SELECT symbol, action, quantity, price, timestamp
                FROM trades
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """, (since,))
            rows = c.fetchall()
            if not rows:
                print("  (No fills in last 24 hours)")
            else:
                for row in rows:
                    symbol, action, qty, price, ts = row
                    print(f"  {ts}: {symbol} {action} {qty} @ {price}")
            conn.close()
        except Exception as e:
            print(f"  ⚠️  Could not query fills: {e}")

    finally:
        ibkr.disconnect()

if __name__ == "__main__":
    show_account_status() 