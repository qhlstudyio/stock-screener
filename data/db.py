import sqlite3
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH


# ─── Connection ───────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Create and return a database connection.
    The database file is created automatically if it does not exist.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn


# ─── Table Setup ──────────────────────────────────────────────────────────────

def create_tables():
    """
    Create all required tables if they do not already exist.
    Safe to run multiple times.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Price history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_prices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            volume      INTEGER,
            UNIQUE(ticker, date)  -- Prevent duplicate entries
        )
    """)

    # Financial data table (one row per ticker, updated on each fetch)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_data (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker              TEXT    NOT NULL UNIQUE,
            market_cap          REAL,
            pe_ratio            REAL,
            eps                 REAL,
            revenue             REAL,
            net_income          REAL,
            gross_profit        REAL,
            total_assets        REAL,
            total_debt          REAL,
            shareholders_equity REAL,
            free_cash_flow      REAL,
            fetched_at          TEXT,
            updated_at          TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("[db] Tables created (or already exist)")


# ─── Save Data ────────────────────────────────────────────────────────────────

def save_stock_prices(ticker: str, df: pd.DataFrame) -> int:
    """
    Save price DataFrame to the database.
    Skips rows that already exist (UNIQUE constraint on ticker + date).

    Returns the number of new rows inserted.
    """
    if df is None or df.empty:
        print(f"[db] {ticker}: no price data to save")
        return 0

    conn   = get_connection()
    cursor = conn.cursor()
    saved  = 0

    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO stock_prices
                    (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                str(row["date"])[:10],  # Keep date portion only (YYYY-MM-DD)
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                int(row["volume"]),
            ))
            if cursor.rowcount > 0:
                saved += 1
        except Exception as e:
            print(f"[db] {ticker}: error saving row {row['date']} — {e}")

    conn.commit()
    conn.close()
    print(f"[db] {ticker}: {saved} new price rows saved")
    return saved


def save_financial_data(data: dict) -> bool:
    """
    Save or update financial data for a ticker.
    Uses INSERT OR REPLACE so re-running always has the latest data.

    Returns True on success, False on failure.
    """
    if data is None:
        return False

    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO financial_data (
                ticker, market_cap, pe_ratio, eps,
                revenue, net_income, gross_profit,
                total_assets, total_debt, shareholders_equity,
                free_cash_flow, fetched_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                market_cap          = excluded.market_cap,
                pe_ratio            = excluded.pe_ratio,
                eps                 = excluded.eps,
                revenue             = excluded.revenue,
                net_income          = excluded.net_income,
                gross_profit        = excluded.gross_profit,
                total_assets        = excluded.total_assets,
                total_debt          = excluded.total_debt,
                shareholders_equity = excluded.shareholders_equity,
                free_cash_flow      = excluded.free_cash_flow,
                fetched_at          = excluded.fetched_at,
                updated_at          = excluded.updated_at
        """, (
            data.get("ticker"),
            data.get("market_cap"),
            data.get("pe_ratio"),
            data.get("eps"),
            data.get("revenue"),
            data.get("net_income"),
            data.get("gross_profit"),
            data.get("total_assets"),
            data.get("total_debt"),
            data.get("shareholders_equity"),
            data.get("free_cash_flow"),
            data.get("fetched_at"),
            datetime.now().isoformat(),
        ))

        conn.commit()
        print(f"[db] {data.get('ticker')}: financial data saved")
        return True

    except Exception as e:
        print(f"[db] Error saving financial data for {data.get('ticker')}: {e}")
        return False

    finally:
        conn.close()


# ─── Query Data ───────────────────────────────────────────────────────────────

def get_stock_prices(ticker: str) -> pd.DataFrame | None:
    """
    Retrieve all price history for a ticker from the database.
    Returns a DataFrame sorted by date ascending, or None if no data found.
    """
    conn = get_connection()

    try:
        df = pd.read_sql_query("""
            SELECT date, open, high, low, close, volume
            FROM stock_prices
            WHERE ticker = ?
            ORDER BY date ASC
        """, conn, params=(ticker,))

        if df.empty:
            return None

        df["date"] = pd.to_datetime(df["date"])
        return df

    except Exception as e:
        print(f"[db] Error reading prices for {ticker}: {e}")
        return None

    finally:
        conn.close()


def get_financial_data(ticker: str) -> dict | None:
    """
    Retrieve financial data for a ticker from the database.
    Returns a dict, or None if no data found.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT * FROM financial_data WHERE ticker = ?
        """, (ticker,))

        row = cursor.fetchone()
        if row is None:
            return None

        return dict(row)

    except Exception as e:
        print(f"[db] Error reading financial data for {ticker}: {e}")
        return None

    finally:
        conn.close()


def get_all_financial_data() -> pd.DataFrame | None:
    """
    Retrieve financial data for all tickers from the database.
    Returns a DataFrame, or None if the table is empty.
    """
    conn = get_connection()

    try:
        df = pd.read_sql_query("""
            SELECT * FROM financial_data ORDER BY ticker ASC
        """, conn)

        if df.empty:
            return None

        return df

    except Exception as e:
        print(f"[db] Error reading all financial data: {e}")
        return None

    finally:
        conn.close()

def get_last_updated(ticker: str, data_type: str = "price") -> str | None:
    """
    Get the last updated timestamp for a ticker.

    data_type options:
        "price"     → checks latest date in stock_prices table
        "financial" → checks updated_at in financial_data table

    Returns a date string (YYYY-MM-DD), or None if no data exists.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        if data_type == "price":
            cursor.execute("""
                SELECT MAX(date) FROM stock_prices WHERE ticker = ?
            """, (ticker,))
        else:
            cursor.execute("""
                SELECT updated_at FROM financial_data WHERE ticker = ?
            """, (ticker,))

        row = cursor.fetchone()
        if row is None or row[0] is None:
            return None

        return str(row[0])[:10]  # Return YYYY-MM-DD only

    except Exception as e:
        print(f"[db] Error getting last updated for {ticker}: {e}")
        return None

    finally:
        conn.close()