# api/dependencies.py
# Shared database helpers used by multiple routers.
#
# All functions return safe defaults (empty list) on DB error — routers are
# responsible for deciding whether an empty result is an error or valid state.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db import get_connection

# Hardcoded SPY display name — used as fallback when financial_data has no
# row for SPY (e.g. bootstrap skipped it for some reason).
_SPY_DISPLAY_NAME = "SPDR S&P 500 ETF Trust"


def get_active_tickers() -> list[str]:
    """
    Return all tickers currently active in the S&P 500 membership table
    (removed_date IS NULL), sorted alphabetically.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ticker
            FROM   sp500_membership
            WHERE  removed_date IS NULL
            ORDER  BY ticker ASC
        """)
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"[dependencies] get_active_tickers error: {e}")
        return []
    finally:
        conn.close()


def get_tickers_by_sector(sector: str) -> list[str]:
    """
    Return tickers in a given GICS sector from financial_data, sorted alphabetically.

    Used by /api/stocks to pre-filter before calling screen_stocks(), which avoids
    building full profiles for all 503 stocks when only one sector is needed.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ticker
            FROM   financial_data
            WHERE  sector = %s
            ORDER  BY ticker ASC
        """, (sector,))
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"[dependencies] get_tickers_by_sector('{sector}') error: {e}")
        return []
    finally:
        conn.close()


def get_tickers_for_search() -> list[dict]:
    """
    Return the lightweight ticker list used by the frontend search autocomplete.

    Includes all active S&P 500 members plus SPY (benchmark).
    SPY is always appended separately with is_benchmark=True so the frontend
    can route it to the dedicated SPY page instead of the standard stock page.

    SPY is explicitly excluded from the membership query to avoid duplication
    in the unlikely event it ends up in sp500_membership by mistake.

    Fields per item:
        ticker       : str   — stock symbol
        company_name : str   — full legal name; falls back to ticker if missing
        sector       : str | None — GICS sector; null for SPY
        is_benchmark : bool  — True only for SPY

    Sorted alphabetically by ticker. Returns [] on DB error.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        # ── S&P 500 members ────────────────────────────────────────────────────
        # LEFT JOIN so members with no financial_data row still appear.
        # COALESCE ensures company_name never falls back to null — ticker is used
        # as the display name if the financial snapshot is missing.
        # SPY is excluded here; it is added separately below.
        cursor.execute("""
            SELECT
                m.ticker,
                COALESCE(f.company_name, m.ticker) AS company_name,
                f.sector
            FROM  sp500_membership m
            LEFT JOIN financial_data f ON m.ticker = f.ticker
            WHERE m.removed_date IS NULL
              AND m.ticker != 'SPY'
            ORDER BY m.ticker ASC
        """)
        rows = cursor.fetchall()
        result = [
            {
                "ticker":       row[0],
                "company_name": row[1],
                "sector":       row[2],
                "is_benchmark": False,
            }
            for row in rows
        ]

        # ── SPY (benchmark) ────────────────────────────────────────────────────
        # Always included regardless of whether financial_data has an SPY row.
        cursor.execute(
            "SELECT company_name FROM financial_data WHERE ticker = 'SPY'"
        )
        spy_row  = cursor.fetchone()
        spy_name = spy_row[0] if (spy_row and spy_row[0]) else _SPY_DISPLAY_NAME

        result.append({
            "ticker":       "SPY",
            "company_name": spy_name,
            "sector":       None,
            "is_benchmark": True,
        })

        return result

    except Exception as e:
        print(f"[dependencies] get_tickers_for_search error: {e}")
        return []
    finally:
        conn.close()