import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging
import os


class DatabaseManager:
    """Manage SQLite database for trade history"""

    def __init__(self, db_path: str = "data/trades.db"):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Connect to SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # Enable column access by name
            self.cursor = self.conn.cursor()
            logging.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            raise

    def create_tables(self):
        """Create necessary tables if they don't exist"""

        # Trades table - records individual trades
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                wallet_id TEXT NOT NULL,
                wallet_name TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL,
                usdt_value REAL,
                order_id TEXT,
                status TEXT DEFAULT 'PENDING',
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Positions table - tracks hedge positions
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                wallet_long TEXT NOT NULL,
                wallet_short TEXT NOT NULL,
                quantity REAL NOT NULL,
                open_time DATETIME NOT NULL,
                close_time DATETIME,
                hold_minutes REAL,
                status TEXT DEFAULT 'OPEN',
                pnl_long REAL,
                pnl_short REAL,
                total_pnl REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Position trades link table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT NOT NULL,
                trade_id TEXT NOT NULL,
                trade_type TEXT NOT NULL,  -- 'OPEN' or 'CLOSE'
                FOREIGN KEY (position_id) REFERENCES positions(position_id),
                FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
            )
        """)

        # Daily summary table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                total_trades INTEGER DEFAULT 0,
                total_volume_usdt REAL DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                successful_trades INTEGER DEFAULT 0,
                failed_trades INTEGER DEFAULT 0,
                unique_symbols TEXT,
                active_wallets TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for better query performance
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_wallet ON trades(wallet_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)")

        self.conn.commit()
        logging.info("Database tables created/verified")

    def record_trade(self, trade_data: dict) -> str:
        """Record a single trade"""
        trade_id = f"{trade_data['symbol']}_{trade_data['wallet_id']}_{datetime.now().timestamp()}"

        try:
            self.cursor.execute("""
                INSERT INTO trades (
                    trade_id, symbol, wallet_id, wallet_name,
                    side, quantity, price, usdt_value,
                    order_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                trade_data['symbol'],
                trade_data['wallet_id'],
                trade_data['wallet_name'],
                trade_data['side'],
                trade_data['quantity'],
                trade_data.get('price', 0),
                trade_data.get('usdt_value', 0),
                trade_data.get('order_id', ''),
                trade_data.get('status', 'SUCCESS')
            ))
            self.conn.commit()
            logging.debug(f"Trade recorded: {trade_id}")
            return trade_id
        except sqlite3.Error as e:
            logging.error(f"Error recording trade: {e}")
            self.conn.rollback()
            return None

    def create_position(self, position_data: dict) -> str:
        """Create a new hedge position record"""
        position_id = f"POS_{position_data['symbol']}_{datetime.now().timestamp()}"

        try:
            self.cursor.execute("""
                INSERT INTO positions (
                    position_id, symbol, wallet_long, wallet_short,
                    quantity, open_time, hold_minutes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_id,
                position_data['symbol'],
                position_data['wallet_long'],
                position_data['wallet_short'],
                position_data['quantity'],
                position_data['open_time'],
                position_data['hold_minutes'],
                'OPEN'
            ))
            self.conn.commit()
            logging.debug(f"Position created: {position_id}")
            return position_id
        except sqlite3.Error as e:
            logging.error(f"Error creating position: {e}")
            self.conn.rollback()
            return None

    def link_trade_to_position(self, position_id: str, trade_id: str, trade_type: str):
        """Link a trade to a position"""
        try:
            self.cursor.execute("""
                INSERT INTO position_trades (position_id, trade_id, trade_type)
                VALUES (?, ?, ?)
            """, (position_id, trade_id, trade_type))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error linking trade to position: {e}")
            self.conn.rollback()

    def close_position(self, position_id: str, pnl_data: dict = None):
        """Mark position as closed and update PnL"""
        try:
            if pnl_data:
                self.cursor.execute("""
                    UPDATE positions
                    SET status = 'CLOSED',
                        close_time = CURRENT_TIMESTAMP,
                        pnl_long = ?,
                        pnl_short = ?,
                        total_pnl = ?
                    WHERE position_id = ?
                """, (
                    pnl_data.get('pnl_long', 0),
                    pnl_data.get('pnl_short', 0),
                    pnl_data.get('total_pnl', 0),
                    position_id
                ))
            else:
                self.cursor.execute("""
                    UPDATE positions
                    SET status = 'CLOSED',
                        close_time = CURRENT_TIMESTAMP
                    WHERE position_id = ?
                """, (position_id,))

            self.conn.commit()
            logging.debug(f"Position closed: {position_id}")
        except sqlite3.Error as e:
            logging.error(f"Error closing position: {e}")
            self.conn.rollback()

    def get_trade_history(self,
                         symbol: str = None,
                         wallet_id: str = None,
                         limit: int = 100) -> List[Dict]:
        """Get trade history with optional filters"""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if wallet_id:
            query += " AND wallet_id = ?"
            params.append(wallet_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logging.error(f"Error fetching trade history: {e}")
            return []

    def get_position_history(self,
                           symbol: str = None,
                           status: str = None,
                           limit: int = 100) -> List[Dict]:
        """Get position history with optional filters"""
        query = "SELECT * FROM positions WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY open_time DESC LIMIT ?"
        params.append(limit)

        try:
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logging.error(f"Error fetching position history: {e}")
            return []

    def get_daily_summary(self, date: str = None) -> Dict:
        """Get daily trading summary"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        try:
            # Get summary from daily_summary table if exists
            self.cursor.execute("""
                SELECT * FROM daily_summary WHERE date = ?
            """, (date,))

            row = self.cursor.fetchone()
            if row:
                return dict(row)

            # Calculate summary from trades if not cached
            self.cursor.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(usdt_value) as total_volume,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COUNT(DISTINCT wallet_id) as active_wallets
                FROM trades
                WHERE DATE(timestamp) = ?
            """, (date,))

            stats = dict(self.cursor.fetchone())

            # Get PnL for the day
            self.cursor.execute("""
                SELECT SUM(total_pnl) as daily_pnl
                FROM positions
                WHERE DATE(close_time) = ? AND status = 'CLOSED'
            """, (date,))

            pnl_data = self.cursor.fetchone()
            stats['daily_pnl'] = pnl_data['daily_pnl'] if pnl_data['daily_pnl'] else 0

            return stats

        except sqlite3.Error as e:
            logging.error(f"Error getting daily summary: {e}")
            return {}

    def get_statistics(self) -> Dict:
        """Get overall trading statistics"""
        try:
            stats = {}

            # Total trades
            self.cursor.execute("SELECT COUNT(*) as count FROM trades")
            stats['total_trades'] = self.cursor.fetchone()['count']

            # Total positions
            self.cursor.execute("SELECT COUNT(*) as count FROM positions")
            stats['total_positions'] = self.cursor.fetchone()['count']

            # Open positions
            self.cursor.execute("SELECT COUNT(*) as count FROM positions WHERE status = 'OPEN'")
            stats['open_positions'] = self.cursor.fetchone()['count']

            # Total PnL
            self.cursor.execute("SELECT SUM(total_pnl) as total FROM positions WHERE status = 'CLOSED'")
            result = self.cursor.fetchone()
            stats['total_pnl'] = result['total'] if result['total'] else 0

            # Success rate
            self.cursor.execute("""
                SELECT
                    COUNT(CASE WHEN total_pnl >= 0 THEN 1 END) as profitable,
                    COUNT(*) as total
                FROM positions
                WHERE status = 'CLOSED'
            """)
            result = self.cursor.fetchone()
            if result['total'] > 0:
                stats['success_rate'] = (result['profitable'] / result['total']) * 100
            else:
                stats['success_rate'] = 0

            # Most traded symbol
            self.cursor.execute("""
                SELECT symbol, COUNT(*) as count
                FROM trades
                GROUP BY symbol
                ORDER BY count DESC
                LIMIT 1
            """)
            result = self.cursor.fetchone()
            if result:
                stats['most_traded_symbol'] = result['symbol']
                stats['most_traded_count'] = result['count']

            return stats

        except sqlite3.Error as e:
            logging.error(f"Error getting statistics: {e}")
            return {}

    def cleanup_old_records(self, days: int = 30):
        """Remove records older than specified days"""
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

            self.cursor.execute("""
                DELETE FROM trades
                WHERE timestamp < datetime(?, 'unixepoch')
            """, (cutoff_date,))

            self.cursor.execute("""
                DELETE FROM positions
                WHERE open_time < datetime(?, 'unixepoch')
            """, (cutoff_date,))

            deleted_trades = self.cursor.rowcount
            self.conn.commit()

            logging.info(f"Cleaned up {deleted_trades} old records")
            return deleted_trades

        except sqlite3.Error as e:
            logging.error(f"Error cleaning up old records: {e}")
            self.conn.rollback()
            return 0

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed")

    def __del__(self):
        """Destructor to ensure connection is closed"""
        self.close()