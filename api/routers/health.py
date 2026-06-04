# api/routers/health.py
# Health check endpoint.
# Used by monitoring tools, deployment verification, and the frontend to
# display a "data as of" timestamp.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from api.schemas import HealthResponse
from data.db import get_connection

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Database connectivity and data freshness",
)
def health_check():
    """
    Returns:
    - **status**: `ok` when the database is reachable and has data.
    - **database**: connection status string.
    - **sp500_member_count**: number of active S&P 500 members in the DB.
    - **latest_price_date**: most recent trading day in stock_prices.
    - **latest_financial_date**: most recent financial data update timestamp.

    Returns HTTP **503** if the database cannot be reached.
    Returns `status: degraded` if the DB is reachable but a query fails.
    """
    # conn is declared before the try block so the finally can always close it
    # safely — even when get_connection() itself raises before assigning conn.
    conn = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM sp500_membership WHERE removed_date IS NULL"
        )
        member_count = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(date) FROM stock_prices")
        latest_price = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(updated_at) FROM financial_data")
        latest_financial = cursor.fetchone()[0]

        return HealthResponse(
            status="ok",
            database="connected",
            sp500_member_count=member_count,
            latest_price_date=str(latest_price)[:10]         if latest_price     else None,
            latest_financial_date=str(latest_financial)[:10] if latest_financial else None,
        )

    except Exception as e:
        # conn is None  → get_connection() itself failed → DB unreachable
        # conn is not None → connected but a query failed → degraded
        if conn is None:
            raise HTTPException(
                status_code=503,
                detail=f"Database unreachable: {e}",
            )
        return HealthResponse(
            status="degraded",
            database=f"error: {e}",
        )

    finally:
        if conn is not None:
            conn.close()
