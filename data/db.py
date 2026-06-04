# data/db.py
# PostgreSQL persistence layer.
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
    Create all required tables if they do not already exist, then apply any
    schema migrations needed for tables that already exist.
    Safe to run multiple times (idempotent).
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # ── stock_prices ───────────────────────────────────────────────────────────
    # Daily price history — includes SPY as market benchmark.
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

    # ── financial_data ─────────────────────────────────────────────────────────
    # Latest financial snapshot — one row per ticker, updated each quarter.
    # Only raw data from yfinance is stored here.
    # Derived ratios (P/S, P/B, ROA, ROIC, D/E, margins, etc.) are calculated
    # at runtime in the analysis layer and are never stored.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_data (
            ticker                  TEXT        NOT NULL,

            -- Identity
            company_name            TEXT,
            exchange                TEXT,
            sector                  TEXT,
            industry                TEXT,

            -- Share data
            shares_outstanding      REAL,

            -- Market pricing
            market_cap              REAL,
            enterprise_value        REAL,
            ev_ebitda               REAL,
            ev_revenue              REAL,
            pe_ratio                REAL,
            forward_pe              REAL,
            eps                     REAL,
            forward_eps             REAL,

            -- Income statement
            revenue                 REAL,
            net_income              REAL,
            gross_profit            REAL,
            operating_income        REAL,
            research_development    REAL,
            interest_expense        REAL,

            -- Balance sheet
            total_assets            REAL,
            total_debt              REAL,
            shareholders_equity     REAL,
            current_assets          REAL,
            current_liabilities     REAL,
            cash_and_equivalents    REAL,

            -- Cash flow
            free_cash_flow          REAL,
            capital_expenditures    REAL,

            -- Dividends
            dividend_yield          REAL,
            dividend_rate           REAL,
            payout_ratio            REAL,

            -- Risk
            beta                    REAL,

            -- Workforce
            full_time_employees     INTEGER,

            -- Analyst consensus
            target_mean_price       REAL,
            target_high_price       REAL,
            target_low_price        REAL,
            analyst_count           INTEGER,
            recommendation_key      TEXT,

            -- Timestamps
            fetched_at              TIMESTAMP,
            updated_at              TIMESTAMP,

            PRIMARY KEY (ticker)
        )
    """)

    # ── Migration: add new columns to existing financial_data table ────────────
    # ADD COLUMN IF NOT EXISTS is idempotent — safe to run on every startup.
    # Applies only to environments where the table was created before these
    # columns were introduced. Fresh installs already have them via CREATE TABLE.
    new_columns = [
        ("company_name",         "TEXT"),
        ("exchange",             "TEXT"),
        ("shares_outstanding",   "REAL"),
        ("enterprise_value",     "REAL"),
        ("ev_ebitda",            "REAL"),
        ("ev_revenue",           "REAL"),
        ("current_assets",       "REAL"),
        ("current_liabilities",  "REAL"),
        ("cash_and_equivalents", "REAL"),
        ("dividend_rate",        "REAL"),
        ("target_high_price",    "REAL"),
        ("target_low_price",     "REAL"),
    ]
    for col_name, col_type in new_columns:
        cursor.execute(
            f"ALTER TABLE financial_data ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
        )

    # ── financial_history ──────────────────────────────────────────────────────
    # Multi-period financial history — unlocks trend and growth analysis.
    # period format : '2024Q4', '2024Q3', '2023', '2022', etc.
    # period_type   : 'quarterly' | 'annual'
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

    # ── sp500_membership ───────────────────────────────────────────────────────
    # S&P 500 constituent tracking.
    # removed_date is NULL while the ticker is still a current member.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sp500_membership (
            ticker          TEXT    NOT NULL,
            added_date      DATE    NOT NULL,
            removed_date    DATE,
            PRIMARY KEY (ticker, added_date)
        )
    """)

    # ── ai_analysis ────────────────────────────────────────────────────────────
    # AI analysis results — schema reserved, not yet implemented.
    # All API endpoints return null for ai_analysis until the AI layer is built.
    # prompt_version enables targeted re-runs when the prompt changes.
    # data_hash detects whether financials have changed since the last analysis.
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
    Insert or update the financial snapshot for one ticker.
    Uses ON CONFLICT DO UPDATE so re-running always stores the latest values.

    The caller (fetcher.py) is responsible for populating all fields.
    Fields absent from the dict default to None / NULL.

    Returns True on success, False on failure.
    """
    if data is None:
        return False

    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO financial_data (
                ticker,
                company_name, exchange, sector, industry,
                shares_outstanding,
                market_cap, enterprise_value, ev_ebitda, ev_revenue,
                pe_ratio, forward_pe, eps, forward_eps,
                revenue, net_income, gross_profit, operating_income,
                research_development, interest_expense,
                total_assets, total_debt, shareholders_equity,
                current_assets, current_liabilities, cash_and_equivalents,
                free_cash_flow, capital_expenditures,
                dividend_yield, dividend_rate, payout_ratio,
                beta,
                full_time_employees,
                target_mean_price, target_high_price, target_low_price,
                analyst_count, recommendation_key,
                fetched_at, updated_at
            ) VALUES (
                %s,
                %s, %s, %s, %s,
                %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s,
                %s,
                %s, %s, %s,
                %s, %s,
                %s, %s
            )
            ON CONFLICT (ticker) DO UPDATE SET
                company_name            = EXCLUDED.company_name,
                exchange                = EXCLUDED.exchange,
                sector                  = EXCLUDED.sector,
                industry                = EXCLUDED.industry,
                shares_outstanding      = EXCLUDED.shares_outstanding,
                market_cap              = EXCLUDED.market_cap,
                enterprise_value        = EXCLUDED.enterprise_value,
                ev_ebitda               = EXCLUDED.ev_ebitda,
                ev_revenue              = EXCLUDED.ev_revenue,
                pe_ratio                = EXCLUDED.pe_ratio,
                forward_pe              = EXCLUDED.forward_pe,
                eps                     = EXCLUDED.eps,
                forward_eps             = EXCLUDED.forward_eps,
                revenue                 = EXCLUDED.revenue,
                net_income              = EXCLUDED.net_income,
                gross_profit            = EXCLUDED.gross_profit,
                operating_income        = EXCLUDED.operating_income,
                research_development    = EXCLUDED.research_development,
                interest_expense        = EXCLUDED.interest_expense,
                total_assets            = EXCLUDED.total_assets,
                total_debt              = EXCLUDED.total_debt,
                shareholders_equity     = EXCLUDED.shareholders_equity,
                current_assets          = EXCLUDED.current_assets,
                current_liabilities     = EXCLUDED.current_liabilities,
                cash_and_equivalents    = EXCLUDED.cash_and_equivalents,
                free_cash_flow          = EXCLUDED.free_cash_flow,
                capital_expenditures    = EXCLUDED.capital_expenditures,
                dividend_yield          = EXCLUDED.dividend_yield,
                dividend_rate           = EXCLUDED.dividend_rate,
                payout_ratio            = EXCLUDED.payout_ratio,
                beta                    = EXCLUDED.beta,
                full_time_employees     = EXCLUDED.full_time_employees,
                target_mean_price       = EXCLUDED.target_mean_price,
                target_high_price       = EXCLUDED.target_high_price,
                target_low_price        = EXCLUDED.target_low_price,
                analyst_count           = EXCLUDED.analyst_count,
                recommendation_key      = EXCLUDED.recommendation_key,
                fetched_at              = EXCLUDED.fetched_at,
                updated_at              = EXCLUDED.updated_at
        """, (
            data.get("ticker"),
            data.get("company_name"),
            data.get("exchange"),
            data.get("sector"),
            data.get("industry"),
            data.get("shares_outstanding"),
            data.get("market_cap"),
            data.get("enterprise_value"),
            data.get("ev_ebitda"),
            data.get("ev_revenue"),
            data.get("pe_ratio"),
            data.get("forward_pe"),
            data.get("eps"),
            data.get("forward_eps"),
            data.get("revenue"),
            data.get("net_income"),
            data.get("gross_profit"),
            data.get("operating_income"),
            data.get("research_development"),
            data.get("interest_expense"),
            data.get("total_assets"),
            data.get("total_debt"),
            data.get("shareholders_equity"),
            data.get("current_assets"),
            data.get("current_liabilities"),
            data.get("cash_and_equivalents"),
            data.get("free_cash_flow"),
            data.get("capital_expenditures"),
            data.get("dividend_yield"),
            data.get("dividend_rate"),
            data.get("payout_ratio"),
            data.get("beta"),
            data.get("full_time_employees"),
            data.get("target_mean_price"),
            data.get("target_high_price"),
            data.get("target_low_price"),
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

    Uses cursor-based fetch instead of pd.read_sql_query to avoid the pandas
    UserWarning about non-SQLAlchemy DBAPI2 connections.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM stock_prices
            WHERE ticker = %s
            ORDER BY date ASC
            """,
            (ticker,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
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
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM financial_data ORDER BY ticker ASC")
        rows = cursor.fetchall()
        if not rows:
            return None

        columns = [desc[0] for desc in cursor.description]
        return pd.DataFrame(rows, columns=columns)

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
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT * FROM financial_history
            WHERE ticker = %s AND period_type = %s
            ORDER BY period ASC
            """,
            (ticker, period_type),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        columns = [desc[0] for desc in cursor.description]
        return pd.DataFrame(rows, columns=columns)

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
    print("db.py — connection test + schema migration")
    print("=" * 55)

    if test_connection():
        create_tables()
        print("\n✅ Database is ready.")
    else:
        print("\n❌ Check DATABASE_URL in your .env file.")