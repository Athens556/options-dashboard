"""SQLite store for simulated trades and caches.

Trades are keyed by (symbol, strategy, date), so re-running a backtest upserts
rather than double-counting. Bayesian beliefs are derived from these rows on
read, not accumulated as counters that drift.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

DB_PATH = os.path.join(os.getcwd(), "market_research.db")


class DBManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Connection that commits on success and always closes."""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
            CREATE TABLE IF NOT EXISTS gym_trades (
                symbol TEXT, strategy TEXT, date TEXT, exit_date TEXT,
                tokens TEXT, signature TEXT, spot REAL, exit_spot REAL, iv REAL,
                pnl REAL, roi REAL, win INTEGER, is_signal INTEGER,
                PRIMARY KEY (symbol, strategy, date)
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_gym_sig ON gym_trades(symbol, signature)")
            conn.execute("""
            CREATE TABLE IF NOT EXISTS trends_cache (
                symbol TEXT PRIMARY KEY, data_json TEXT, last_updated TEXT
            )""")

    def upsert_trades(self, trades: pd.DataFrame):
        if trades.empty:
            return
        rows = zip(
            trades["symbol"], trades["strategy"],
            trades["date"].dt.strftime("%Y-%m-%d"), trades["exit_date"].dt.strftime("%Y-%m-%d"),
            (json.dumps(t) for t in trades["tokens"]), trades["signature"],
            trades["spot"].astype(float), trades["exit_spot"].astype(float), trades["iv"].astype(float),
            trades["pnl"].astype(float), trades["roi"].astype(float),
            trades["win"].astype(int), trades["is_signal"].astype(int),
        )
        with self.get_connection() as conn:
            conn.executemany("INSERT OR REPLACE INTO gym_trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

    def load_trades(self, symbol=None) -> pd.DataFrame:
        query, params = "SELECT * FROM gym_trades", ()
        if symbol:
            query, params = query + " WHERE symbol = ?", (symbol,)
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"])
        df["exit_date"] = pd.to_datetime(df["exit_date"])
        df["tokens"] = df["tokens"].map(json.loads)
        df["win"] = df["win"].astype(bool)
        df["is_signal"] = df["is_signal"].astype(bool)
        return df

    def trade_count(self) -> int:
        with self.get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM gym_trades").fetchone()[0]

    def beliefs(self, symbol: str, signature: str) -> dict:
        """strategy -> (wins, losses) over all stored days that shared this core signature."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT strategy, SUM(win), COUNT(*) - SUM(win) FROM gym_trades "
                "WHERE symbol = ? AND signature = ? GROUP BY strategy", (symbol, signature)).fetchall()
        return {name: (int(w), int(l)) for name, w, l in rows}

    def reset_trades(self):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM gym_trades")

    def get_trends_cache(self, symbol):
        """Cached Google Trends payload if under 24h old."""
        cutoff = (datetime.now() - pd.Timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            row = conn.execute("SELECT data_json FROM trends_cache WHERE symbol=? AND last_updated > ?",
                               (symbol, cutoff)).fetchone()
        return json.loads(row[0]) if row else None

    def save_trends_cache(self, symbol, data_json):
        with self.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO trends_cache (symbol, data_json, last_updated) VALUES (?, ?, ?)",
                         (symbol, json.dumps(data_json), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
