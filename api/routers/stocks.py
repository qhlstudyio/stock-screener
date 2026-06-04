# api/routers/stocks.py
# Stock endpoints with in-memory result caching.
#
# Performance problem (pre-fix):
#   screen_stocks() calls build_stock_profile() per ticker, which runs
#   several DB queries + pandas calculations each time. 83 IT stocks × ~3
#   queries = 249 DB round-trips + risk metric calculations → 10-15 seconds.
#
# Solution — two-level cache:
#   _sector_cache : caches the full list of profiles per sector (1-hour TTL).
#                   First IT request is slow; every subsequent request in the
#                   same server session is in-memory filter + sort (< 5ms).
#   _stock_cache  : caches individual stock profiles (30-min TTL).
#                   First visit to /stock/AAPL is slow; repeat visits instant.
#
# Cache is in-process memory. Cleared on server restart.
# daily_updater runs overnight; the 1-hour TTL ensures stale data is
# never shown for more than one hour after a daytime financial refresh.

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException, Query
from typing import Annotated

from api.schemas import TickerItem, StockProfile
from api.dependencies import (
    get_active_tickers,
    get_tickers_by_sector,
    get_tickers_for_search,
)
from analysis.screener import build_stock_profile, screen_stocks


router = APIRouter(tags=["Stocks"])


# ── Cache configuration ────────────────────────────────────────────────────────

# { sector_name: (timestamp, [profile_dict, ...]) }
_sector_cache: dict[str, tuple[float, list]] = {}

# { ticker: (timestamp, profile_dict) }
_stock_cache: dict[str, tuple[float, dict]] = {}

CACHE_TTL_SECTOR = 3600   # seconds — 1 hour per sector list
CACHE_TTL_STOCK  = 1800   # seconds — 30 minutes per individual stock


def _cache_get(cache: dict, key: str, ttl: int):
    """Return cached value if it exists and has not expired, else None."""
    if key in cache:
        ts, data = cache[key]
        if time.time() - ts < ttl:
            return data
    return None


def _cache_set(cache: dict, key: str, data) -> None:
    cache[key] = (time.time(), data)


# ── Sortable fields ────────────────────────────────────────────────────────────

_SORTABLE_FIELDS: frozenset[str] = frozenset({
    "score", "market_cap", "pe_ratio", "forward_pe",
    "gross_margin", "operating_margin", "profit_margin", "fcf_margin",
    "roe", "roa", "roic", "debt_ratio", "current_ratio",
    "interest_coverage", "revenue_per_employee",
    "beta", "volatility", "sharpe", "alpha", "max_drawdown",
    "return_1y", "return_6m", "vs_spy_1y", "vs_spy_6m",
    "dividend_yield",
})

_NO_SECTOR_DEFAULT_LIMIT = 50
_NO_SECTOR_MAX_LIMIT     = 500


# ── In-memory filter & sort ────────────────────────────────────────────────────
# Applied to cached profiles instead of re-running the full screener.

def _passes_filters(p: dict, filters: dict) -> bool:
    """Return True if profile p satisfies all active filters."""
    if 'sector'            in filters and p.get('sector')          != filters['sector']:             return False
    if 'min_score'         in filters and (p.get('score')       or 0) < filters['min_score']:        return False
    if 'max_pe'            in filters and p.get('pe_ratio') is not None \
                                      and p['pe_ratio']            > filters['max_pe']:              return False
    if 'min_roe'           in filters and (p.get('roe')         or 0) < filters['min_roe']:          return False
    if 'max_debt_ratio'    in filters and (p.get('debt_ratio')  or 1) > filters['max_debt_ratio']:   return False
    if 'min_profit_margin' in filters and (p.get('profit_margin') or 0) < filters['min_profit_margin']: return False
    if 'min_gross_margin'  in filters and (p.get('gross_margin')  or 0) < filters['min_gross_margin']:  return False
    if 'max_beta'          in filters and p.get('beta') is not None \
                                      and p['beta']                > filters['max_beta']:             return False
    return True


def _apply_sort(profiles: list, sort_by: str, ascending: bool) -> list:
    """Sort profiles in-memory. Nulls always go last."""
    return sorted(
        profiles,
        key=lambda p: (p.get(sort_by) is None, p.get(sort_by) or 0),
        reverse=not ascending,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/tickers",
    response_model=list[TickerItem],
    summary="Lightweight ticker list for search autocomplete",
)
def get_tickers():
    """
    All S&P 500 members + SPY. Fetched once on app load and filtered client-side.
    ~503 items, < 40 KB JSON.
    """
    tickers = get_tickers_for_search()
    if not tickers:
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve ticker list. Database may be unavailable.",
        )
    return [TickerItem.model_validate(t) for t in tickers]


@router.get(
    "/stocks",
    response_model=list[StockProfile],
    summary="Screen S&P 500 stocks by fundamental metrics",
    description=(
        "Filter and sort S&P 500 stocks. "
        "**Sector filter strongly recommended** — results are cached per sector "
        "so the first request for a sector is slow (~5-15s) but all subsequent "
        "requests (including filter/sort changes) are served from memory in < 5ms. "
        "Ratio/margin filters use **decimal form**: `min_roe=0.15` = ROE ≥ 15%."
    ),
)
def get_stocks(
    sector: Annotated[str | None, Query(description="GICS sector (exact). See /api/sectors.")] = None,
    min_score:         Annotated[float | None, Query(ge=0, le=100)] = None,
    max_pe:            Annotated[float | None, Query(gt=0)]         = None,
    min_roe:           Annotated[float | None, Query()]             = None,
    max_debt_ratio:    Annotated[float | None, Query(ge=0, le=1)]   = None,
    min_profit_margin: Annotated[float | None, Query()]             = None,
    min_gross_margin:  Annotated[float | None, Query()]             = None,
    max_beta:          Annotated[float | None, Query(gt=0)]         = None,
    sort_by:           Annotated[str,          Query()]             = "score",
    ascending:         Annotated[bool,         Query()]             = False,
    limit:             Annotated[int,          Query(gt=0, le=_NO_SECTOR_MAX_LIMIT)] = _NO_SECTOR_DEFAULT_LIMIT,
):
    if sort_by not in _SORTABLE_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort_by: '{sort_by}'. Allowed: {sorted(_SORTABLE_FIELDS)}",
        )

    # ── Determine ticker scope ────────────────────────────────────────────────
    if sector:
        cache_key = f"sector::{sector}"

        # Try cache first
        cached = _cache_get(_sector_cache, cache_key, CACHE_TTL_SECTOR)
        if cached is None:
            # Cache miss — build all profiles for this sector (slow path, once per TTL)
            tickers = get_tickers_by_sector(sector)
            if not tickers:
                return []
            # screen_stocks with no filters; we apply filters below from cache
            raw_profiles = screen_stocks(
                tickers=tickers,
                filters={},
                sort_by='score',
                ascending=False,
            )
            _cache_set(_sector_cache, cache_key, raw_profiles)
            cached = raw_profiles

        # Apply filters and sort in-memory (fast path — always)
        filters: dict = {}
        if sector             is not None: filters['sector']            = sector
        if min_score          is not None: filters['min_score']         = min_score
        if max_pe             is not None: filters['max_pe']            = max_pe
        if min_roe            is not None: filters['min_roe']           = min_roe
        if max_debt_ratio     is not None: filters['max_debt_ratio']    = max_debt_ratio
        if min_profit_margin  is not None: filters['min_profit_margin'] = min_profit_margin
        if min_gross_margin   is not None: filters['min_gross_margin']  = min_gross_margin
        if max_beta           is not None: filters['max_beta']          = max_beta

        profiles = [p for p in cached if _passes_filters(p, filters)]
        profiles = _apply_sort(profiles, sort_by, ascending)

    else:
        # No sector — limited pool (alphabetical first N, no caching for simplicity)
        tickers  = get_active_tickers()[:limit]
        filters  = {}
        profiles = screen_stocks(tickers=tickers, filters=filters,
                                 sort_by=sort_by, ascending=ascending)
        profiles = profiles[:limit]

    return [StockProfile.model_validate(p) for p in profiles]


@router.get(
    "/stock/{ticker}",
    response_model=StockProfile,
    summary="Full profile for one stock",
)
def get_stock(ticker: str):
    """
    Full fundamental profile for a single ticker. Cached for 30 minutes.
    First visit is slow (DB queries + risk calculations); repeat visits instant.
    Ticker is case-insensitive.
    """
    t = ticker.upper()

    # Try cache first
    cached = _cache_get(_stock_cache, t, CACHE_TTL_STOCK)
    if cached is not None:
        return StockProfile.model_validate(cached)

    # Cache miss — build the profile (slow path)
    profile = build_stock_profile(t)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No data found for '{t}'. "
                "The ticker may not be in the S&P 500 or bootstrap has not run."
            ),
        )

    _cache_set(_stock_cache, t, profile)
    return StockProfile.model_validate(profile)