import sqlite3

conn = sqlite3.connect('trade_logs.db')

print("Tables in database:")
for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';"):
    print(row)

print("\nOpen SELL orders in orders table:")
for row in conn.execute("SELECT order_id, price, quantity, timestamp FROM orders WHERE action='SELL' ORDER BY timestamp DESC;"):
    print(row)

print("\nCancelled/filled SELL orders (status='Cancelled' or 'Filled'):")
for row in conn.execute("SELECT order_id, price, quantity, timestamp, status FROM orders WHERE action='SELL' AND status IN ('Cancelled', 'Filled') ORDER BY timestamp DESC;"):
    print(row)

print("\nAll trades in trades table:")
trades = conn.execute("SELECT trade_id, symbol, action, price, quantity, timestamp FROM trades ORDER BY timestamp DESC;").fetchall()
for trade in trades:
    trade_id, symbol, action, price, quantity, timestamp = trade
    # Check for matching order
    order = conn.execute("SELECT id FROM orders WHERE order_id = ?", (trade_id,)).fetchone()
    has_order = bool(order)
    # Check for matching order status
    order_status = conn.execute("SELECT status FROM orders WHERE order_id = ?", (trade_id,)).fetchone()
    has_order = bool(order_status)
    status_str = order_status[0] if has_order else "NO MATCH (!!!)"
    print(f"trade_id={trade_id}, {action} {quantity} {symbol} @ {price} [{timestamp}] -- {status_str}")

conn.close() 