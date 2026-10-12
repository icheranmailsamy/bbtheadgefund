import sqlite3
import pandas as pd
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../trades.db")

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Accounts Table
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT UNIQUE,
        broker TEXT,
        api_key TEXT,
        api_secret TEXT,
        contracts INTEGER DEFAULT 3,
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )''')

    # Trades Table
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT,
        trade_time TEXT,
        asset TEXT,
        side TEXT,
        entry_price REAL,
        exit_price REAL,
        pnl_points REAL,
        pnl_usd REAL,
        contracts INTEGER,
        execution_type TEXT
    )''')

    # System State Table
    c.execute('''CREATE TABLE IF NOT EXISTS system_state (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    conn.commit()
    conn.close()

# Account Operations
def get_accounts():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM accounts", conn)
    conn.close()
    return df

def add_account(name, broker, api_key, api_secret, contracts=3):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT OR REPLACE INTO accounts 
                 (account_name, broker, api_key, api_secret, contracts, is_active, created_at)
                 VALUES (?, ?, ?, ?, ?, 1, ?)''',
              (name, broker, api_key, api_secret, contracts, now))
    conn.commit()
    conn.close()

def toggle_account_status(account_id, is_active):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE accounts SET is_active = ? WHERE id = ?", (int(is_active), int(account_id)))
    conn.commit()
    conn.close()

def delete_account(account_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM accounts WHERE id = ?", (int(account_id),))
    conn.commit()
    conn.close()

# Trade Operations
def log_trade_record(account_name, asset, side, entry_p, exit_p, pts, pnl_usd, contracts, exec_type="LIVE_RTH"):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT INTO trades 
                 (account_name, trade_time, asset, side, entry_price, exit_price, pnl_points, pnl_usd, contracts, execution_type)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (account_name, now, asset, side, entry_p, exit_p, pts, pnl_usd, contracts, exec_type))
    conn.commit()
    conn.close()

def get_trades_df():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM trades ORDER BY trade_time DESC", conn)
    conn.close()
    if not df.empty:
        df['trade_time'] = pd.to_datetime(df['trade_time'])
    return df

# System State Operations
def get_system_state(key, default=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM system_state WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_system_state(key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

init_db()
