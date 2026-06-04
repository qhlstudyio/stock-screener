# data/bootstrap.py
# One-time script to load 5 years of historical data for all S&P 500 stocks.
#
# Run this once to populate the database before starting daily_updater.
# Safe to interrupt and re-run — all steps check existing data first.
#
# Usage:
#   python data/bootstrap.py              # full run (~3-4 hours)
#   python data/bootstrap.py --limit 10   # test run with first 10 tickers
#   python data/bootstrap.py --ticker AAPL MSFT GOOGL  # specific tickers only

import sys
import os
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.fetcher import get_stock_price, get_financial_data, get_financial_history, get_sp500_tickers
from data.db import (
    create_tables,
    save_stock_prices,
    save_financial_data,
    save_financial_history,
    get_last_updated,
    get_connection,
)


# ── Constants ──────────────────────────────────────────────────────────────────

PRICE_HISTORY_DAYS  = 5 * 365   # 5 years of daily price data
SLEEP_BETWEEN       = 2.0       # seconds between tickers (rate limit protection)
BENCHMARK_TICKER    = "SPY"     # always included, not added to sp500_membership


# ── S&P 500 membership helpers ─────────────────────────────────────────────────

def _get_current_members_from_db() -> set[str]:
    """Return the set of tickers currently marked as S&P 500 members in the DB."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ticker FROM sp500_membership
            WHERE removed_date IS NULL
        """)
        return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()
    finally:
        conn.close()


def _record_sp500_membership(tickers: list[str]) -> None:
    """
    Sync the sp500_membership table with the current ticker list.
    - New members get an added_date = today, removed_date = NULL.
    - Tickers no longer in the list get removed_date = today.
    """
    today  = datetime.today().date()
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        current_in_db = _get_current_members_from_db()
        new_set       = set(tickers)

        # Mark newly added tickers
        added = new_set - current_in_db
        for ticker in added:
            cursor.execute("""
                INSERT INTO sp500_membership (ticker, added_date, removed_date)
                VALUES (%s, %s, NULL)
                ON CONFLICT (ticker, added_date) DO NOTHING
            """, (ticker, today))

        # Mark removed tickers
        removed = current_in_db - new_set
        for ticker in removed:
            cursor.execute("""
                UPDATE sp500_membership
                SET removed_date = %s
                WHERE ticker = %s AND removed_date IS NULL
            """, (today, ticker))

        conn.commit()
        print(f"[bootstrap] Membership sync: {len(added)} added, {len(removed)} removed")

    except Exception as e:
        print(f"[bootstrap] Membership sync error: {e}")
    finally:
        conn.close()


# ── Per-ticker loader ──────────────────────────────────────────────────────────

def _needs_price_update(ticker: str) -> bool:
    """True if the ticker has no price data at all in the DB."""
    last = get_last_updated(ticker, data_type="price")
    return last is None


def _needs_financial_update(ticker: str) -> bool:
    """True if the ticker has no financial snapshot in the DB."""
    last = get_last_updated(ticker, data_type="financial")
    return last is None


def load_ticker(ticker: str, force: bool = False) -> dict:
    """
    Load all data for a single ticker into the database.

    Steps:
      1. Price history  — skipped if already present (unless force=True)
      2. Financial snapshot — skipped if already present (unless force=True)
      3. Financial history  — always attempted (ON CONFLICT DO NOTHING handles duplicates)

    Returns a status dict:
      { ticker, price, financial, history_records }
    """
    status = {
        "ticker":          ticker,
        "price":           "skipped",
        "financial":       "skipped",
        "history_records": 0,
    }

    # Step 1: Price history
    if force or _needs_price_update(ticker):
        df = get_stock_price(ticker, days=PRICE_HISTORY_DAYS)
        if df is not None:
            save_stock_prices(ticker, df)
            status["price"] = "updated"
        else:
            status["price"] = "failed"
    else:
        print(f"[bootstrap] {ticker}: price data already present, skipping")

    # Step 2: Financial snapshot
    if force or _needs_financial_update(ticker):
        data = get_financial_data(ticker)
        if data is not None:
            save_financial_data(data)
            status["financial"] = "updated"
        else:
            status["financial"] = "failed"
    else:
        print(f"[bootstrap] {ticker}: financial data already present, skipping")

    # Step 3: Financial history (always run — ON CONFLICT DO NOTHING is safe)
    records = get_financial_history(ticker)
    if records:
        saved = save_financial_history(ticker, records)
        status["history_records"] = saved

    return status


# ── Main ───────────────────────────────────────────────────────────────────────

def run(tickers: list[str], force: bool = False) -> None:
    """
    Load data for all tickers in sequence with rate-limit protection.
    Prints a live progress line and a summary at the end.
    """
    total   = len(tickers)
    results = []
    failed  = []

    print(f"\n[bootstrap] Starting: {total} tickers  "
          f"({'forced refresh' if force else 'resume mode'})\n")

    for i, ticker in enumerate(tickers, start=1):
        print(f"── [{i}/{total}] {ticker} {'─' * max(0, 30 - len(ticker))}")
        try:
            status = load_ticker(ticker, force=force)
            results.append(status)
            if status["price"] == "failed" or status["financial"] == "failed":
                failed.append(ticker)
        except Exception as e:
            print(f"[bootstrap] {ticker}: unexpected error — {e}")
            failed.append(ticker)

        # Rate limit: pause between tickers, skip after the last one
        if i < total:
            time.sleep(SLEEP_BETWEEN)

    # Summary
    price_updated     = sum(1 for r in results if r["price"]     == "updated")
    price_failed      = sum(1 for r in results if r["price"]     == "failed")
    financial_updated = sum(1 for r in results if r["financial"] == "updated")
    financial_failed  = sum(1 for r in results if r["financial"] == "failed")
    total_history     = sum(r["history_records"] for r in results)

    print(f"\n{'=' * 55}")
    print(f"  Bootstrap complete")
    print(f"{'=' * 55}")
    print(f"  Tickers processed    : {len(results)}")
    print(f"  Price — updated      : {price_updated}")
    print(f"  Price — failed       : {price_failed}")
    print(f"  Financial — updated  : {financial_updated}")
    print(f"  Financial — failed   : {financial_failed}")
    print(f"  History rows saved   : {total_history}")

    if failed:
        print(f"\n  Failed tickers ({len(failed)}):")
        for t in failed:
            print(f"    {t}")
        print(f"\n  Re-run with: python data/bootstrap.py --ticker {' '.join(failed)}")

    print(f"{'=' * 55}\n")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Bootstrap historical data for all S&P 500 stocks."
    )
    parser.add_argument(
        "--ticker", nargs="+", metavar="TICKER",
        help="Load specific tickers only (e.g. --ticker AAPL MSFT)"
    )
    parser.add_argument(
        "--limit", type=int, metavar="N",
        help="Load only the first N tickers (for testing)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch all data even if already present in the DB"
    )
    args = parser.parse_args()

    # Ensure all tables exist before writing anything
    print("[bootstrap] Verifying database tables...")
    create_tables()

    # Determine ticker list
    if args.ticker:
        # Explicit list from command line
        tickers = [t.upper() for t in args.ticker]
        print(f"[bootstrap] Mode: explicit tickers ({len(tickers)})")
    else:
        # Full S&P 500 from Wikipedia
        print("[bootstrap] Fetching S&P 500 ticker list from Wikipedia...")
        tickers = get_sp500_tickers()
        if not tickers:
            print("[bootstrap] ERROR: Could not fetch S&P 500 list. Check network and retry.")
            sys.exit(1)

        if args.limit:
            tickers = tickers[:args.limit]
            print(f"[bootstrap] Mode: first {args.limit} tickers (test run)")
        else:
            print(f"[bootstrap] Mode: full S&P 500 ({len(tickers)} tickers)")

    # Always include SPY as the market benchmark (price only, not in membership)
    if BENCHMARK_TICKER not in tickers:
        tickers = [BENCHMARK_TICKER] + tickers

    # Sync S&P 500 membership table (exclude SPY — it's not an S&P 500 member)
    sp500_only = [t for t in tickers if t != BENCHMARK_TICKER]
    if not args.ticker:
        # Only sync membership when running against the full list
        _record_sp500_membership(sp500_only)

    # Run
    run(tickers, force=args.force)
