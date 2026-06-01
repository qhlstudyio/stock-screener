# data/db.py
# PostgreSQL persistence layer, replacing the original SQLite version.
# All public function signatures are unchanged so upstream modules
# (metrics, valuation, screener) require no modification.

import os
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection() -> psycopg2.extensions.connection:
    """
    Create and return a PostgreSQL database connection.
    The connection string is read from the DATABASE_URL environment variable.
    """
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please check your .env file."
        )
    return psycopg2.connect(DATABASE_URL)


# ── Table Setup ────────────────────────────────────────────────────────────────

def create_tables() -> None:
    """
    Create all required tables if they do not already exist.
    Safe to run multiple times (idempotent).
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # Daily price history — includes SPY as market benchmark
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_prices (
            ticker  TEXT    NOT NULL,
            date    DATE    NOT NULL,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  BIGINT,
            PRIMARY KEY (ticker, date)
        )
    """)

    # Latest financial snapshot — one row per ticker, updated each quarter
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_data (
            ticker                  TEXT        NOT NULL,
            sector                  TEXT,
            industry                TEXT,
            market_cap              REAL,
            pe_ratio                REAL,
            forward_pe              REAL,
            eps                     REAL,
            forward_eps             REAL,
            revenue                 REAL,
            net_income              REAL,
            gross_profit            REAL,
            operating_income        REAL,
            total_assets            REAL,
            total_debt              REAL,
            shareholders_equity     REAL,
            free_cash_flow          REAL,
            capital_expenditures    REAL,
            research_development    REAL,
            interest_expense        REAL,
            full_time_employees     INTEGER,
            dividend_yield          REAL,
            payout_ratio            REAL,
            beta                    REAL,
            target_mean_price       REAL,
            analyst_count           INTEGER,
            recommendation_key      TEXT,
            fetched_at              TIMESTAMP,
            updated_at              TIMESTAMP,
            PRIMARY KEY (ticker)
        )
    """)

    # Multi-period financial history — unlocks trend analysis
    # period format: '2024Q4', '2024Q3', '2023', etc.
    # period_type:   'quarterly' | 'annual'
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_history (
            ticker                  TEXT    NOT NULL,
            period                  TEXT    NOT NULL,
            period_type             TEXT    NOT NULL,
            revenue                 REAL,
            net_income              REAL,
            gross_profit            REAL,
            operating_income        REAL,
            free_cash_flow          REAL,
            total_assets            REAL,
            total_debt              REAL,
            shareholders_equity     REAL,
            fetched_at              TIMESTAMP,
            PRIMARY KEY (ticker, period, period_type)
        )
    """)

    # S&P 500 constituent tracking — removed_date is NULL while still a member
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sp500_membership (
            ticker          TEXT    NOT NULL,
            added_date      DATE    NOT NULL,
            removed_date    DATE,
            PRIMARY KEY (ticker, added_date)
        )
    """)

    # AI analysis results — schema reserved, not yet implemented.
    # API endpoints return null for ai_analysis until the AI layer is built.
    # prompt_version enables targeted re-runs when the prompt changes.
    # data_hash detects whether financials have changed since last analysis.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis (
            ticker              TEXT    NOT NULL,
            analysis_date       DATE    NOT NULL,
            metrics_insight     TEXT,
            valuation_insight   TEXT,
            risk_flags          TEXT,
            overall_insight     TEXT,
            overall_sentiment   TEXT,
            model_used          TEXT,
            prompt_version      TEXT,
            tokens_used         INTEGER,
            data_hash           TEXT,
            created_at          TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (ticker, analysis_date)
        )
    """)

    conn.commit()
    conn.close()
    print("[db] All tables are ready.")


# ── Write ──────────────────────────────────────────────────────────────────────

def save_stock_prices(ticker: str, df: pd.DataFrame) -> int:
    """
    Persist a price DataFrame to stock_prices.
    Rows that already exist are silently skipped (ON CONFLICT DO NOTHING).

    Returns the number of newly inserted rows.
    """
    if df is None or df.empty:
        print(f"[db] {ticker}: no price data to save.")
        return 0

    conn   = get_connection()
    cursor = conn.cursor()
    saved  = 0

    for _, row in df.iterrows():
        try:
            # Guard against NaN volume values from yfinance
            volume = int(row["volume"]) if pd.notna(row.get("volume")) else None

            cursor.execute("""
                INSERT INTO stock_prices
                    (ticker, date, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO NOTHING
            """, (
                ticker,
                str(row["date"])[:10],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                volume,
            ))
            if cursor.rowcount > 0:
                saved += 1
        except Exception as e:
            print(f"[db] {ticker}: error saving row {row['date']} — {e}")

    conn.commit()
    conn.close()
    print(f"[db] {ticker}: {saved} new price rows saved.")
    return saved


def save_financial_data(data: dict) -> bool:
    """
    Insert or update financial data for one ticker.
    Uses ON CONFLICT DO UPDATE so re-running always stores the latest values.

    Returns True on success, False on failure.
    """
    if data is None:
        return False

    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO financial_data (
                ticker, sector, industry,
                market_cap, pe_ratio, forward_pe, eps, forward_eps,
                revenue, net_income, gross_profit, operating_income,
                total_assets, total_debt, shareholders_equity,
                free_cash_flow, capital_expenditures, research_development,
                interest_expense, full_time_employees,
                dividend_yield, payout_ratio, beta,
                target_mean_price, analyst_count, recommendation_key,
                fetched_at, updated_at
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (ticker) DO UPDATE SET
                sector                = EXCLUDED.sector,
                industry              = EXCLUDED.industry,
                market_cap            = EXCLUDED.market_cap,
                pe_ratio              = EXCLUDED.pe_ratio,
                forward_pe            = EXCLUDED.forward_pe,
                eps                   = EXCLUDED.eps,
                forward_eps           = EXCLUDED.forward_eps,
                revenue               = EXCLUDED.revenue,
                net_income            = EXCLUDED.net_income,
                gross_profit          = EXCLUDED.gross_profit,
                operating_income      = EXCLUDED.operating_income,
                total_assets          = EXCLUDED.total_assets,
                total_debt            = EXCLUDED.total_debt,
                shareholders_equity   = EXCLUDED.shareholders_equity,
                free_cash_flow        = EXCLUDED.free_cash_flow,
                capital_expenditures  = EXCLUDED.capital_expenditures,
                research_development  = EXCLUDED.research_development,
                interest_expense      = EXCLUDED.interest_expense,
                full_time_employees   = EXCLUDED.full_time_employees,
                dividend_yield        = EXCLUDED.dividend_yield,
                payout_ratio          = EXCLUDED.payout_ratio,
                beta                  = EXCLUDED.beta,
                target_mean_price     = EXCLUDED.target_mean_price,
                analyst_count         = EXCLUDED.analyst_count,
                recommendation_key    = EXCLUDED.recommendation_key,
                fetched_at            = EXCLUDED.fetched_at,
                updated_at            = EXCLUDED.updated_at
        """, (
            data.get("ticker"),
            data.get("sector"),
            data.get("industry"),
            data.get("market_cap"),
            data.get("pe_ratio"),
            data.get("forward_pe"),
            data.get("eps"),
            data.get("forward_eps"),
            data.get("revenue"),
            data.get("net_income"),
            data.get("gross_profit"),
            data.get("operating_income"),
            data.get("total_assets"),
            data.get("total_debt"),
            data.get("shareholders_equity"),
            data.get("free_cash_flow"),
            data.get("capital_expenditures"),
            data.get("research_development"),
            data.get("interest_expense"),
            data.get("full_time_employees"),
            data.get("dividend_yield"),
            data.get("payout_ratio"),
            data.get("beta"),
            data.get("target_mean_price"),
            data.get("analyst_count"),
            data.get("recommendation_key"),
            data.get("fetched_at"),
            datetime.now().isoformat(),
        ))

        conn.commit()
        print(f"[db] {data.get('ticker')}: financial data saved.")
        return True

    except Exception as e:
        print(f"[db] Error saving financial data for {data.get('ticker')}: {e}")
        return False

    finally:
        conn.close()


def save_financial_history(ticker: str, records: list) -> int:
    """
    Persist quarterly or annual financial history records.
    Each item in records is a dict with one period's data.
    Existing records are skipped (ON CONFLICT DO NOTHING).

    Returns the number of newly inserted rows.
    """
    if not records:
        return 0

    conn   = get_connection()
    cursor = conn.cursor()
    saved  = 0

    for record in records:
        try:
            cursor.execute("""
                INSERT INTO financial_history (
                    ticker, period, period_type,
                    revenue, net_income, gross_profit, operating_income,
                    free_cash_flow, total_assets, total_debt,
                    shareholders_equity, fetched_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, period, period_type) DO NOTHING
            """, (
                ticker,
                record.get("period"),
                record.get("period_type"),
                record.get("revenue"),
                record.get("net_income"),
                record.get("gross_profit"),
                record.get("operating_income"),
                record.get("free_cash_flow"),
                record.get("total_assets"),
                record.get("total_debt"),
                record.get("shareholders_equity"),
                datetime.now().isoformat(),
            ))
            if cursor.rowcount > 0:
                saved += 1
        except Exception as e:
            print(f"[db] {ticker}: error saving history record "
                  f"{record.get('period')} — {e}")

    conn.commit()
    conn.close()
    print(f"[db] {ticker}: {saved} new history rows saved.")
    return saved


# ── Read ───────────────────────────────────────────────────────────────────────

def get_stock_prices(ticker: str) -> pd.DataFrame | None:
    """
    Retrieve the full price history for a ticker, sorted by date ascending.
    Columns: date, open, high, low, close, volume.
    Returns None if no data is found.
    """
    conn = get_connection()

    try:
        df = pd.read_sql_query(
            """
            SELECT date, open, high, low, close, volume
            FROM stock_prices
            WHERE ticker = %s
            ORDER BY date ASC
            """,
            conn,
            params=(ticker,),
        )

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
    Retrieve the latest financial snapshot for a ticker.
    Returns a plain dict, or None if no record exists.
    """
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute(
            "SELECT * FROM financial_data WHERE ticker = %s",
            (ticker,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None

    except Exception as e:
        print(f"[db] Error reading financial data for {ticker}: {e}")
        return None

    finally:
        conn.close()


def get_all_financial_data() -> pd.DataFrame | None:
    """
    Retrieve the latest financial snapshot for every ticker.
    Returns a DataFrame sorted by ticker, or None if the table is empty.
    """
    conn = get_connection()

    try:
        df = pd.read_sql_query(
            "SELECT * FROM financial_data ORDER BY ticker ASC",
            conn,
        )
        return df if not df.empty else None

    except Exception as e:
        print(f"[db] Error reading all financial data: {e}")
        return None

    finally:
        conn.close()


def get_financial_history(
    ticker: str,
    period_type: str = "quarterly",
) -> pd.DataFrame | None:
    """
    Retrieve multi-period financial history for a ticker.

    Parameters
    ----------
    ticker      : stock ticker symbol
    period_type : 'quarterly' (default) | 'annual'

    Returns a DataFrame sorted by period ascending, or None if no data exists.
    """
    conn = get_connection()

    try:
        df = pd.read_sql_query(
            """
            SELECT * FROM financial_history
            WHERE ticker = %s AND period_type = %s
            ORDER BY period ASC
            """,
            conn,
            params=(ticker, period_type),
        )
        return df if not df.empty else None

    except Exception as e:
        print(f"[db] Error reading financial history for {ticker}: {e}")
        return None

    finally:
        conn.close()


def get_last_updated(ticker: str, data_type: str = "price") -> str | None:
    """
    Return the most recent data date for a ticker.

    Parameters
    ----------
    ticker    : stock ticker symbol
    data_type : 'price' (default) checks stock_prices.date
                'financial'      checks financial_data.updated_at

    Returns a YYYY-MM-DD string, or None if no data exists.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        if data_type == "price":
            cursor.execute(
                "SELECT MAX(date) FROM stock_prices WHERE ticker = %s",
                (ticker,),
            )
        else:
            cursor.execute(
                "SELECT updated_at FROM financial_data WHERE ticker = %s",
                (ticker,),
            )

        row = cursor.fetchone()
        if row is None or row[0] is None:
            return None

        return str(row[0])[:10]  # YYYY-MM-DD only

    except Exception as e:
        print(f"[db] Error getting last updated date for {ticker}: {e}")
        return None

    finally:
        conn.close()


# ── Health check ───────────────────────────────────────────────────────────────

def test_connection() -> bool:
    """
    Verify that the database connection is reachable.
    Returns True on success, False on failure.
    """
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        conn.close()
        print(f"[db] Connection OK: {version[:60]}...")
        return True
    except Exception as e:
        print(f"[db] Connection failed: {e}")
        return False


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("db.py — connection test")
    print("=" * 55)

    if test_connection():
        create_tables()
        print("\n✅ Database is ready.")
    else:
        print("\n❌ Check DATABASE_URL in your .env file.")