# api/routers/prices.py
# Historical price data endpoint.
# Used by the frontend PriceChart component for both individual stocks and SPY.
#
# GET /api/prices/{ticker}?period=1y
#   Returns close prices for the requested period, ordered by date ascending.
#   Both ticker and SPY are fetched separately by the frontend; the backend
#   returns raw close data and the frontend normalises to % return.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import date, timedelta
from fastapi  import APIRouter, HTTPException, Query
from typing   import Annotated

from api.schemas import PricePoint
from data.db     import get_connection

router = APIRouter(tags=["Prices"])

# Number of calendar days each period label maps to.
# Slightly over-fetches (calendar days > trading days) so we always get
# the requested number of trading sessions.
PERIOD_DAYS: dict[str, int] = {
    '1m':  35,
    '3m':  95,
    '6m': 185,
    '1y': 370,
    '2y': 740,
    '5y': 1830,
}


@router.get(
    "/prices/{ticker}",
    response_model=list[PricePoint],
    summary="Historical close prices for one ticker",
    description=(
        "Returns daily close prices for the requested time period. "
        "Use `period` to control the lookback window: "
        "`1m`, `3m`, `6m`, `1y`, `2y`, `5y`. "
        "Works for any ticker with data in `stock_prices`, including `SPY`."
    ),
)
def get_prices(
    ticker: str,
    period: Annotated[
        str,
        Query(description="Time period: 1m | 3m | 6m | 1y | 2y | 5y"),
    ] = "1y",
):
    ticker = ticker.upper()

    if period not in PERIOD_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid period '{period}'. Allowed: {list(PERIOD_DAYS.keys())}",
        )

    start = date.today() - timedelta(days=PERIOD_DAYS[period])

    conn = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, close, volume
            FROM   stock_prices
            WHERE  ticker = %s AND date >= %s
            ORDER  BY date ASC
            """,
            (ticker, start),
        )
        rows = cursor.fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No price data found for '{ticker}'. "
                    "The ticker may not be in the database or bootstrap has not run."
                ),
            )

        return [
            PricePoint(
                date=str(row[0])[:10],
                close=round(float(row[1]), 4),
                volume=int(row[2]) if row[2] is not None else None,
            )
            for row in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Price query failed: {e}")
    finally:
        if conn:
            conn.close()
