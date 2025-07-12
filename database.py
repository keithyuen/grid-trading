# grid-trading/database.py

import sqlite3
from datetime import datetime

class TradeDB:
    def __init__(self, db_path):
        self.db_path = db_path
        # self.conn = sqlite3.connect(db_path)  # Remove persistent connection for safety
        self._create_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        with self._get_conn() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                action TEXT,
                price REAL,
                quantity INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                order_id INTEGER,
                status TEXT DEFAULT 'Open'
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                action TEXT,
                price REAL,
                quantity INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                trade_id INTEGER
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                position REAL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS pnl (
                symbol TEXT PRIMARY KEY,
                realized REAL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS latest_prices (
                symbol TEXT PRIMARY KEY,
                price REAL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )''')
            # Drop cancels table if it exists
            conn.execute('DROP TABLE IF EXISTS cancels')
            conn.commit()

    def record_trade(self, symbol, action, price, quantity, trade_id=None):
        with self._get_conn() as conn:
            conn.execute(
                'INSERT INTO trades (symbol, action, price, quantity, timestamp, trade_id) VALUES (?, ?, ?, ?, ?, ?)',
                (symbol, action, price, quantity, datetime.utcnow().isoformat(), trade_id)
            )

    def record_order(self, symbol, action, price, quantity, order_id=None):
        with self._get_conn() as conn:
            conn.execute('INSERT INTO orders (symbol, action, price, quantity, timestamp, order_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                              (symbol, action, price, quantity, datetime.utcnow().isoformat(), order_id, 'Open'))

    def update_order_status(self, order_id, status):
        with self._get_conn() as conn:
            conn.execute('UPDATE orders SET status = ? WHERE order_id = ?', (status, order_id))

    def get_committed_cash(self, symbol):
        """Get total cash committed to open buy orders"""
        with self._get_conn() as conn:
            result = conn.execute('SELECT SUM(price * quantity) FROM orders WHERE symbol = ? AND action = "BUY" AND status = "Open"', (symbol,)).fetchone()
            return result[0] if result[0] else 0.0

    def record_realized_pnl(self, symbol, sell_price, quantity):
        """Record realized PnL from a sell trade"""
        with self._get_conn() as conn:
            # Get average buy price for this symbol
            avg_buy = conn.execute(
                'SELECT AVG(price) FROM trades WHERE symbol = ? AND action = "BUY"', (symbol,)).fetchone()[0] or 0.0
            realized = (sell_price - avg_buy) * quantity
            current = self.get_realized_pnl(symbol)
            updated = current + realized
            conn.execute('REPLACE INTO pnl (symbol, realized) VALUES (?, ?)', (symbol, updated))

    def get_realized_pnl(self, symbol):
        """Get total realized PnL for a symbol"""
        with self._get_conn() as conn:
            result = conn.execute('SELECT realized FROM pnl WHERE symbol = ?', (symbol,)).fetchone()
            return result[0] if result else 0.0

    def get_open_orders(self):
        """Get all open orders (status='Open') as list of dictionaries"""
        with self._get_conn() as conn:
            result = conn.execute('''
                SELECT symbol, action, price, quantity, order_id, timestamp
                FROM orders 
                WHERE status = 'Open'
                ORDER BY timestamp DESC
            ''').fetchall()
            return [
                {
                    'symbol': row[0],
                    'action': row[1], 
                    'price': row[2],
                    'quantity': row[3],
                    'order_id': row[4],
                    'timestamp': row[5]
                }
                for row in result
            ]

    def get_trade_history(self, symbol, limit=100):
        """Get recent trade history for a symbol"""
        with self._get_conn() as conn:
            result = conn.execute('SELECT * FROM trades WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?', (symbol, limit)).fetchall()
            return result

    def clear_old_orders(self, symbol):
        """Clear old order records (keep only recent ones)"""
        with self._get_conn() as conn:
            # Keep only orders from the last 7 days
            cutoff_date = datetime.utcnow().isoformat()
            conn.execute('DELETE FROM orders WHERE symbol = ? AND timestamp < ?', (symbol, cutoff_date))

    def clear_all(self):
        """Delete all records from orders, trades, positions, and other relevant tables."""
        conn = self._get_conn()
        try:
            conn.execute('DELETE FROM orders')
            conn.execute('DELETE FROM trades')
            conn.execute('DELETE FROM positions')
            # Add more tables here if needed
            conn.commit()
        finally:
            conn.close()

    def get_position(self, symbol):
        conn = self._get_conn()
        try:
            row = conn.execute('SELECT position FROM positions WHERE symbol = ?', (symbol,)).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def get_all_positions(self):
        conn = self._get_conn()
        try:
            rows = conn.execute('SELECT symbol, position FROM positions').fetchall()
            return [{"symbol": r[0], "position": r[1]} for r in rows]
        finally:
            conn.close()

    def update_position(self, symbol, position):
        with self._get_conn() as conn:
            conn.execute(
                'REPLACE INTO positions (symbol, position) VALUES (?, ?)',
                (symbol, position)
            )

    def order_exists(self, symbol, action, price, quantity, order_id=None):
        with self._get_conn() as conn:
            if order_id is not None:
                row = conn.execute('SELECT 1 FROM orders WHERE order_id = ?', (order_id,)).fetchone()
                if row:
                    return True
            row = conn.execute('SELECT 1 FROM orders WHERE symbol = ? AND action = ? AND price = ? AND quantity = ?',
                               (symbol, action, price, quantity)).fetchone()
            return bool(row)

    def trade_exists(self, symbol, action, price, quantity, trade_id=None):
        with self._get_conn() as conn:
            if trade_id is not None:
                row = conn.execute('SELECT 1 FROM trades WHERE trade_id = ?', (trade_id,)).fetchone()
                if row:
                    return True
            row = conn.execute('SELECT 1 FROM trades WHERE symbol = ? AND action = ? AND price = ? AND quantity = ?',
                               (symbol, action, price, quantity)).fetchone()
            return bool(row)

    def cancel_exists(self, symbol, action, price, quantity, order_id=None):
        """Check if an order has been cancelled (status='Cancelled')"""
        with self._get_conn() as conn:
            if order_id is not None:
                row = conn.execute('SELECT 1 FROM orders WHERE order_id = ? AND status = "Cancelled"', (order_id,)).fetchone()
                if row:
                    return True
            row = conn.execute('SELECT 1 FROM orders WHERE symbol = ? AND action = ? AND price = ? AND quantity = ? AND status = "Cancelled"',
                               (symbol, action, price, quantity)).fetchone()
            return bool(row)

    def set_latest_price(self, symbol, price):
        with self._get_conn() as conn:
            conn.execute(
                'REPLACE INTO latest_prices (symbol, price, timestamp) VALUES (?, ?, ?)',
                (symbol, price, datetime.utcnow().isoformat())
            )

    def get_latest_price(self, symbol):
        with self._get_conn() as conn:
            row = conn.execute('SELECT price FROM latest_prices WHERE symbol = ?', (symbol,)).fetchone()
            return row[0] if row else None

    def count_open_orders(self, symbol, action):
        """Count open orders for a symbol and action (BUY/SELL)"""
        with self._get_conn() as conn:
            # Count orders with status='Open'
            result = conn.execute('''
                SELECT COUNT(*) FROM orders 
                WHERE symbol = ? AND action = ? AND status = 'Open'
            ''', (symbol, action)).fetchone()
            return result[0] if result else 0

    def order_has_fill(self, order_id):
        with self._get_conn() as conn:
            result = conn.execute('SELECT 1 FROM trades WHERE trade_id = ?', (order_id,)).fetchone()
            return bool(result)

    def mark_order_filled(self, order_id):
        """Mark an order as filled by updating status to 'Filled'"""
        with self._get_conn() as conn:
            conn.execute('UPDATE orders SET status = ? WHERE order_id = ?', ('Filled', order_id))

    def record_cancel(self, symbol, action, price, quantity, order_id=None):
        """Record a cancelled order by updating status to 'Cancelled'"""
        with self._get_conn() as conn:
            if order_id is not None:
                conn.execute('UPDATE orders SET status = ? WHERE order_id = ?', ('Cancelled', order_id))
            else:
                # If no order_id, we can't update, so this method is mainly for order_id-based cancels
                pass

    def get_trade_by_order_id(self, order_id):
        with self._get_conn() as conn:
            row = conn.execute('SELECT symbol, action, price, quantity, timestamp, trade_id FROM trades WHERE trade_id = ?', (order_id,)).fetchone()
            if row:
                return {
                    'symbol': row[0],
                    'action': row[1],
                    'price': row[2],
                    'quantity': row[3],
                    'timestamp': row[4],
                    'trade_id': row[5]
                }
            return None
