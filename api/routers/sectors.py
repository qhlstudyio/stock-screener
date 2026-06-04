# api/routers/sectors.py
# Sector list with aggregate financial statistics.
#
# GET /api/sectors — all GICS sectors + per-sector stats
#
# Stats are computed directly in SQL from raw financial_data — no profile
# building required. This is intentional: computing per-sector ratios in SQL
# is a fast, single-query operation that avoids the 503-ticker profile overhead.
# The values are not stored anywhere — they are derived on the fly.
#
# Outlier handling:
#   avg_pe_ratio      — excludes PE ≤ 0 and PE > 500
#   avg_roe           — excludes values outside [−200%, +500%] to reduce
#                       distortion from buyback-inflated or negative-equity companies
#   avg_gross_margin  — excludes rows where revenue = 0 (div-by-zero protection)
#   avg_profit_margin — same as gross_margin
#   median_market_cap — median is used instead of mean (more robust to outliers)

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from api.schemas import SectorStats
from data.db import get_connection

router = APIRouter(tags=["Sectors"])


@router.get(
    "/sectors",
    response_model=list[SectorStats],
    summary="All GICS sectors with aggregate statistics",
)
def get_sectors():
    """
    Returns all GICS sectors present in the database with lightweight aggregate
    financial statistics. Computed from one SQL query — no per-ticker profile
    building is involved.

    **Caveats:**
    - Stats reflect the raw financial snapshots, not adjusted metrics.
    - avg_roe excludes extreme outliers (e.g. MCD with negative equity).
    - avg_pe_ratio excludes loss-making and hyper-growth outliers (PE > 500).
    - These aggregates are approximate and intended for screening context,
      not rigorous sector analysis.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                sector,
                COUNT(*)  AS ticker_count,

                -- P/E: exclude loss-making (PE ≤ 0) and extreme outliers (PE > 500)
                AVG(pe_ratio)
                    FILTER (WHERE pe_ratio > 0 AND pe_ratio < 500)
                    AS avg_pe_ratio,

                -- Gross margin: gross_profit / revenue; skip zero-revenue rows
                AVG(gross_profit / NULLIF(revenue, 0))
                    FILTER (WHERE gross_profit IS NOT NULL
                              AND revenue      IS NOT NULL
                              AND revenue      != 0)
                    AS avg_gross_margin,

                -- Profit margin: net_income / revenue; can be legitimately negative
                AVG(net_income / NULLIF(revenue, 0))
                    FILTER (WHERE net_income IS NOT NULL
                              AND revenue    IS NOT NULL
                              AND revenue    != 0)
                    AS avg_profit_margin,

                -- ROE: exclude negative equity (undefined) and extreme buyback cases
                -- BETWEEN -2 AND 5 = between -200% and +500%
                AVG(net_income / NULLIF(shareholders_equity, 0))
                    FILTER (WHERE net_income           IS NOT NULL
                              AND shareholders_equity  >  0
                              AND net_income / NULLIF(shareholders_equity, 0)
                                  BETWEEN -2 AND 5)
                    AS avg_roe,

                -- Median market cap (robust to outliers like NVDA / AAPL)
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY market_cap)
                    FILTER (WHERE market_cap IS NOT NULL)
                    AS median_market_cap

            FROM  financial_data
            WHERE sector IS NOT NULL
            GROUP BY sector
            ORDER BY sector ASC
        """)

        rows    = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        return [
            SectorStats.model_validate(dict(zip(columns, row)))
            for row in rows
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute sector statistics: {e}",
        )

    finally:
        conn.close()
