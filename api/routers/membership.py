# api/routers/membership.py
# S&P 500 membership tracking endpoint.
#
# GET /api/sp500/membership — current member count + recent additions/removals
#
# Data comes from the sp500_membership table, which is maintained by
# daily_updater.py and populated initially by bootstrap.py.
#
# Bootstrap note:
#   On the day bootstrap runs, ALL tickers are inserted with added_date = today.
#   So for the first `lookback_days` days after bootstrap, recent_added will
#   contain all 500+ tickers. This is expected behaviour — not a bug.
#   After the first daily_updater run, only real index changes appear.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Query
from typing import Annotated

from api.schemas import MembershipResponse, MembershipEvent
from data.db import get_connection

router = APIRouter(tags=["Membership"])

_DEFAULT_LOOKBACK_DAYS = 90
_MAX_LOOKBACK_DAYS     = 365


@router.get(
    "/sp500/membership",
    response_model=MembershipResponse,
    summary="Current S&P 500 membership and recent index changes",
)
def get_membership(
    lookback_days: Annotated[
        int,
        Query(
            ge=1,
            le=_MAX_LOOKBACK_DAYS,
            description="How many calendar days back to search for additions and removals.",
        ),
    ] = _DEFAULT_LOOKBACK_DAYS,
):
    """
    Returns:
    - **current_count**: number of active S&P 500 members in the database.
    - **as_of**: today's date (YYYY-MM-DD).
    - **recent_added**: tickers added to the index within the last `lookback_days` days.
    - **recent_removed**: tickers removed within the same window.

    Both lists are ordered most-recent first.

    **Bootstrap note:** On the day bootstrap runs, all ~503 tickers are inserted
    with today as their `added_date`. For the first `lookback_days` days after
    bootstrap, `recent_added` will therefore contain all members. This is
    expected and resolves naturally as the lookback window moves forward.
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        # Current active member count
        cursor.execute(
            "SELECT COUNT(*) FROM sp500_membership WHERE removed_date IS NULL"
        )
        current_count = cursor.fetchone()[0]

        # Recent additions (ordered newest first)
        cursor.execute(
            """
            SELECT ticker, added_date
            FROM   sp500_membership
            WHERE  added_date >= %s
            ORDER  BY added_date DESC, ticker ASC
            """,
            (cutoff,),
        )
        recent_added = [
            MembershipEvent(ticker=row[0], date=str(row[1])[:10])
            for row in cursor.fetchall()
        ]

        # Recent removals (ordered newest first)
        cursor.execute(
            """
            SELECT ticker, removed_date
            FROM   sp500_membership
            WHERE  removed_date IS NOT NULL
              AND  removed_date >= %s
            ORDER  BY removed_date DESC, ticker ASC
            """,
            (cutoff,),
        )
        recent_removed = [
            MembershipEvent(ticker=row[0], date=str(row[1])[:10])
            for row in cursor.fetchall()
        ]

        return MembershipResponse(
            current_count=current_count,
            as_of=str(date.today()),
            recent_added=recent_added,
            recent_removed=recent_removed,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Membership query failed: {e}",
        )

    finally:
        conn.close()
