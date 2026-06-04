# api/main.py
# FastAPI application entry point.
#
# Start locally:
#   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
#
# Cache warmup:
#   On startup, all sector caches are pre-warmed concurrently so users never
#   experience slow first loads after a server restart.
#
#   WARMUP_CONCURRENCY controls how many sectors are built in parallel:
#     3  — safe default (recommended for Oracle Free Tier ARM)
#     5  — fine for local dev or beefier machines
#   Total warmup time ≈ ceil(11 / concurrency) × slowest_sector_time
#   At concurrency=3: ~3 rounds × 15s ≈ 45 seconds
#   At concurrency=5: ~2 rounds × 15s ≈ 30 seconds

import sys
import os
import asyncio
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.routers import health, stocks, sectors, membership, prices

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Max sectors computed in parallel during warmup.
# Lower = gentler on the DB and CPU; higher = faster warmup.
# 3 is a safe default for Oracle Free Tier ARM (4 vCPU, 24 GB RAM).
WARMUP_CONCURRENCY = 3


# ── Cache warmup ───────────────────────────────────────────────────────────────

async def _warmup_one(
    sector:    str,
    index:     int,
    total:     int,
    semaphore: asyncio.Semaphore,
) -> None:
    """
    Pre-warm the cache for one sector.
    Uses a semaphore to limit how many sectors run concurrently.
    """
    from api.routers.stocks import _sector_cache, _cache_set
    from api.dependencies import get_tickers_by_sector
    from analysis.screener import screen_stocks

    async with semaphore:
        cache_key = f"sector::{sector}"

        # Another task or a user request may have populated the cache already
        if cache_key in _sector_cache:
            print(f"[warmup] [{index}/{total}] {sector} — already cached, skipping")
            return

        tickers = get_tickers_by_sector(sector)
        if not tickers:
            print(f"[warmup] [{index}/{total}] {sector} — no tickers, skipping")
            return

        try:
            loop = asyncio.get_running_loop()

            def _build(t=tickers):
                return screen_stocks(tickers=t, filters={}, sort_by='score', ascending=False)

            profiles = await loop.run_in_executor(None, _build)
            _cache_set(_sector_cache, cache_key, profiles)
            print(f"[warmup] [{index}/{total}] {sector} — {len(profiles)} stocks ✓")

        except Exception as e:
            print(f"[warmup] [{index}/{total}] {sector} — ERROR: {e}")


async def _warmup_all_sectors() -> None:
    """
    Pre-warm all sector caches concurrently (up to WARMUP_CONCURRENCY at a time).

    Sectors are sorted by size (largest first) so the biggest ones don't end
    up as straggler tasks at the very end.

    The server is fully operational throughout — this runs in the background
    and never blocks the event loop or any user requests.
    """
    from data.db import get_connection

    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sector, COUNT(*) AS n
            FROM   financial_data
            WHERE  sector IS NOT NULL
            GROUP  BY sector
            ORDER  BY n DESC, sector ASC
        """)
        sector_list = [row[0] for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print(f"[warmup] Could not fetch sector list: {e}")
        return

    if not sector_list:
        print("[warmup] No sectors found — skipping warmup.")
        return

    total     = len(sector_list)
    semaphore = asyncio.Semaphore(WARMUP_CONCURRENCY)

    print(
        f"[warmup] Pre-warming {total} sectors "
        f"({WARMUP_CONCURRENCY} concurrent)…"
    )

    # Launch all sector tasks concurrently; semaphore limits active workers
    tasks = [
        _warmup_one(sector, i, total, semaphore)
        for i, sector in enumerate(sector_list, 1)
    ]
    await asyncio.gather(*tasks)

    print("[warmup] All sector caches ready.")


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create warmup task — runs in background, server accepts requests immediately
    asyncio.create_task(_warmup_all_sectors())
    yield
    # Nothing to clean up on shutdown


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Stock Screener API",
    version="1.0.0",
    description=(
        "S&P 500 fundamental analysis API. "
        "All data is end-of-day (EOD). "
        "The `ai_analysis` field is reserved and returns null. "
        "Sector results are cached in memory (1-hour TTL); "
        "individual stock profiles are cached for 30 minutes. "
        "All sector caches are pre-warmed on server startup."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router,     prefix="/api")
app.include_router(stocks.router,     prefix="/api")
app.include_router(sectors.router,    prefix="/api")
app.include_router(membership.router, prefix="/api")
app.include_router(prices.router,     prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")