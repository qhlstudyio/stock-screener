# data/daily_updater.py
# Cron job — runs after market close (16:30 EST, Mon–Fri).
#
# Suggested crontab entry (server time must be EST, or adjust accordingly):
#   30 16 * * 1-5  cd /path/to/project && /path/to/venv/bin/python data/daily_updater.py >> logs/updater.log 2>&1
#
# What this script does, in order:
#   [1/5]  Fetch current S&P 500 list from Wikipedia
#   [2/5]  Sync sp500_membership table (additions + removals)
#   [3/5]  Backfill new / returning members (5yr prices + financials + history)
#   [4/5]  Update daily prices for all active members + SPY
#   [5/5]  Refresh financial snapshot + history for stale entries (> 90 days)
#
# Abort conditions (no data is written):
#   - Wikipedia returns fewer than MIN_SP500_COUNT tickers (network / parsing issue)
#   - Database is unreachable at startup
#
# Usage:
#   python data/daily_updater.py                         # normal cron run
#   python data/daily_updater.py --force                 # force all updates
#   python data/daily_updater.py --ticker AAPL MSFT      # manual: specific tickers only
#   python data/daily_updater.py --dry-run               # preview changes, no writes

import sys
import os
import time
import argparse
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Alias the yfinance-facing functions to avoid name collision with db.py functions
# that share the same logical name but read from the database instead.
from data.fetcher import (
    get_stock_price,
    get_financial_data      as fetch_financial_snapshot,
    get_financial_history   as fetch_financial_history,
    get_sp500_tickers,
)
from data.db import (
    create_tables,
    test_connection,
    get_connection,
    save_stock_prices,
    save_financial_data,
    save_financial_history,
    get_last_updated,
)


# ── Constants ──────────────────────────────────────────────────────────────────

PRICE_DAYS_DAILY       = 7       # calendar-day window for routine price pulls
                                  # (7 days catches up to a week of missed sessions)
PRICE_DAYS_BACKFILL    = 5 * 365 # 5-year window for new / returning members
FINANCIAL_REFRESH_DAYS = 90      # days before a financial snapshot is considered stale
SLEEP_BETWEEN          = 2.0     # seconds between yfinance calls (rate-limit guard)
BENCHMARK_TICKER       = "SPY"   # always updated; intentionally not in sp500_membership
MIN_SP500_COUNT        = 490     # Wikipedia safety floor; abort if below this


# ── Membership helpers ─────────────────────────────────────────────────────────

def _get_active_members() -> set[str]:
    """
    Return the set of tickers currently active in S&P 500
    (i.e. rows in sp500_membership where removed_date IS NULL).
    """
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT ticker FROM sp500_membership WHERE removed_date IS NULL"
        )
        return {row[0] for row in cursor.fetchall()}
    except Exception as e:
        print(f"[updater] ERROR reading active members: {e}")
        return set()
    finally:
        conn.close()


def _sync_membership(sp500_tickers: list[str]) -> tuple[set[str], set[str]]:
    """
    Diff the freshly fetched S&P 500 list against sp500_membership and apply
    the delta atomically.

    - Tickers in Wikipedia but NOT in DB  → INSERT with added_date = today
    - Tickers in DB but NOT in Wikipedia  → UPDATE removed_date = today
    - Returning tickers (previously removed and now back) are treated the same
      as new additions: a fresh row is inserted with today as added_date.
      The old row (with removed_date set) stays intact for audit history.

    Returns (newly_added, newly_removed).
    On any DB error: rolls back and returns (set(), set()) — no data is written.

    NOTE: Only call this after verifying len(sp500_tickers) >= MIN_SP500_COUNT.
    """
    today         = date.today()
    current_in_db = _get_active_members()
    new_set       = set(sp500_tickers)
    newly_added   = new_set - current_in_db
    newly_removed = current_in_db - new_set

    conn   = get_connection()
    cursor = conn.cursor()
    try:
        for ticker in newly_added:
            cursor.execute("""
                INSERT INTO sp500_membership (ticker, added_date, removed_date)
                VALUES (%s, %s, NULL)
                ON CONFLICT (ticker, added_date) DO NOTHING
            """, (ticker, today))

        for ticker in newly_removed:
            cursor.execute("""
                UPDATE sp500_membership
                SET    removed_date = %s
                WHERE  ticker = %s AND removed_date IS NULL
            """, (today, ticker))

        conn.commit()
        return newly_added, newly_removed

    except Exception as e:
        print(f"[updater] ERROR during membership sync: {e}")
        conn.rollback()
        return set(), set()

    finally:
        conn.close()


# ── Staleness checks ───────────────────────────────────────────────────────────

def _price_is_stale(ticker: str) -> bool:
    """
    True if no price row exists for today (or no price data at all).
    On weekends / holidays the last price will be a past trading day; this
    correctly returns True, we attempt a fetch, yfinance returns no new rows,
    and save_stock_prices() silently skips them via ON CONFLICT DO NOTHING.
    """
    last = get_last_updated(ticker, data_type="price")
    if last is None:
        return True
    return datetime.strptime(last, "%Y-%m-%d").date() < date.today()


def _financial_is_stale(ticker: str) -> bool:
    """
    True if the financial snapshot is older than FINANCIAL_REFRESH_DAYS, or missing.
    """
    last = get_last_updated(ticker, data_type="financial")
    if last is None:
        return True
    age = (date.today() - datetime.strptime(last, "%Y-%m-%d").date()).days
    return age > FINANCIAL_REFRESH_DAYS


# ── Per-ticker operations ──────────────────────────────────────────────────────

def _backfill_ticker(ticker: str) -> dict:
    """
    Full historical load for a new or returning S&P 500 member.
    Always fetches 5yr prices, the latest financial snapshot, and all history.
    No staleness guard — the caller (Step 3) decides when to invoke this.

    Returns a status dict compatible with bootstrap.load_ticker's output:
        { ticker, price, financial, history_records }
    """
    status = {
        "ticker":          ticker,
        "price":           "skipped",
        "financial":       "skipped",
        "history_records": 0,
    }

    df = get_stock_price(ticker, days=PRICE_DAYS_BACKFILL)
    if df is not None:
        save_stock_prices(ticker, df)
        status["price"] = "updated"
    else:
        status["price"] = "failed"

    data = fetch_financial_snapshot(ticker)
    if data is not None:
        save_financial_data(data)
        status["financial"] = "updated"
    else:
        status["financial"] = "failed"

    records = fetch_financial_history(ticker)
    if records:
        saved = save_financial_history(ticker, records)
        status["history_records"] = saved

    return status


def _update_price(ticker: str, force: bool = False) -> str:
    """
    Fetch and store the most recent price data using a 7-day window.
    The 7-day window catches any sessions missed due to failures or holidays.
    save_stock_prices() uses ON CONFLICT DO NOTHING, so duplicates are harmless.

    Args:
        force: If True, fetch even when today's data is already present.

    Returns 'updated' | 'skipped' | 'failed'.
    """
    if not force and not _price_is_stale(ticker):
        return "skipped"

    df = get_stock_price(ticker, days=PRICE_DAYS_DAILY)
    if df is not None:
        save_stock_prices(ticker, df)
        return "updated"
    return "failed"


def _update_financial(ticker: str, force: bool = False) -> str:
    """
    Refresh the financial snapshot and history when stale (or forced).
    ON CONFLICT DO UPDATE in save_financial_data() always stores the latest.
    ON CONFLICT DO NOTHING in save_financial_history() skips existing periods.

    Args:
        force: If True, refresh even when data is within FINANCIAL_REFRESH_DAYS.

    Returns 'updated' | 'skipped' | 'failed'.
    """
    if not force and not _financial_is_stale(ticker):
        return "skipped"

    data = fetch_financial_snapshot(ticker)
    if data is None:
        return "failed"

    save_financial_data(data)

    # Pull history after the snapshot so new quarterly periods are captured.
    records = fetch_financial_history(ticker)
    if records:
        save_financial_history(ticker, records)

    return "updated"


# ── Main run ───────────────────────────────────────────────────────────────────

def run(force: bool = False) -> None:
    """
    Execute the full daily update sequence (Steps 1–5).

    Args:
        force: If True, ignore staleness thresholds and refresh all data.
               Useful after a multi-day outage or a fetcher.py bug fix.
    """
    run_start = datetime.now()
    print(f"\n{'=' * 60}")
    print(f"  daily_updater  {run_start.strftime('%Y-%m-%d %H:%M:%S')}"
          f"{'  [FORCED]' if force else ''}")
    print(f"{'=' * 60}\n")

    # ── Step 1: Fetch current S&P 500 ──────────────────────────────────────────
    print("[1/5] Fetching S&P 500 list from Wikipedia...")
    sp500_tickers = get_sp500_tickers()

    if len(sp500_tickers) < MIN_SP500_COUNT:
        print(
            f"\n[updater] ABORT — Wikipedia returned only {len(sp500_tickers)} "
            f"tickers (minimum expected: {MIN_SP500_COUNT}).\n"
            f"          This usually means a network issue or a Wikipedia "
            f"table-format change.\n"
            f"          No data has been written to the database."
        )
        return

    print(f"      → {len(sp500_tickers)} tickers\n")

    # ── Step 2: Sync membership ─────────────────────────────────────────────────
    print("[2/5] Syncing sp500_membership...")
    newly_added, newly_removed = _sync_membership(sp500_tickers)

    if newly_added:
        print(f"      → Added   ({len(newly_added)}): {sorted(newly_added)}")
    if newly_removed:
        print(f"      → Removed ({len(newly_removed)}): {sorted(newly_removed)}")
    if not newly_added and not newly_removed:
        print("      → No membership changes today")
    print()

    # ── Step 3: Backfill new / returning members ────────────────────────────────
    # Read the updated member list here so we always work from the DB's
    # authoritative state, even if _sync_membership partially failed.
    active_members = _get_active_members()

    backfill_failed = []
    if newly_added:
        print(f"[3/5] Backfilling {len(newly_added)} new member(s)...")
        for i, ticker in enumerate(sorted(newly_added), start=1):
            print(f"      [{i}/{len(newly_added)}] {ticker}")
            try:
                s = _backfill_ticker(ticker)
                print(
                    f"        price={s['price']}  "
                    f"financial={s['financial']}  "
                    f"history={s['history_records']} rows"
                )
                if s["price"] == "failed" or s["financial"] == "failed":
                    backfill_failed.append(ticker)
            except Exception as e:
                print(f"        ERROR: {e}")
                backfill_failed.append(ticker)

            if i < len(newly_added):
                time.sleep(SLEEP_BETWEEN)
        print()
    else:
        print("[3/5] No new members to backfill\n")

    # ── Step 4: Daily price update ──────────────────────────────────────────────
    # active_members now reflects post-sync state:
    #   - includes newly added members (just backfilled → price_is_stale = False → skipped)
    #   - excludes removed members (no longer updated)
    price_tickers = sorted(active_members) + [BENCHMARK_TICKER]
    print(f"[4/5] Updating prices — {len(price_tickers)} tickers "
          f"({len(active_members)} members + SPY)...")

    price_counts = {"updated": 0, "skipped": 0, "failed": 0}
    price_failed = []

    for i, ticker in enumerate(price_tickers, start=1):
        result = "failed"   # pre-set so the sleep condition is correct if an
        try:                # exception fires before _update_price returns
            result = _update_price(ticker, force=force)
            price_counts[result] += 1
            if result == "failed":
                price_failed.append(ticker)
        except Exception as e:
            print(f"      [{ticker}] unexpected error: {e}")
            price_counts["failed"] += 1
            price_failed.append(ticker)

        if i % 100 == 0:
            print(f"      ... {i}/{len(price_tickers)} done")

        # Only sleep when an actual yfinance call was made.
        # Skipping "skipped" tickers avoids unnecessary wait on re-runs.
        if result in ("updated", "failed") and i < len(price_tickers):
            time.sleep(SLEEP_BETWEEN)

    print(f"      → updated={price_counts['updated']}  "
          f"skipped={price_counts['skipped']}  "
          f"failed={price_counts['failed']}")
    if price_failed:
        print(f"      → Failures: {price_failed}")
    print()

    # Guard against back-to-back yfinance calls at the Step 4 → 5 boundary.
    # The last price ticker skips its trailing sleep (i < len condition), so if
    # it made an API call we insert a pause here before Step 5 begins.
    if price_counts["updated"] + price_counts["failed"] > 0:
        time.sleep(SLEEP_BETWEEN)

    # ── Step 5: Financial refresh ───────────────────────────────────────────────
    threshold_label = "forced" if force else f"> {FINANCIAL_REFRESH_DAYS}d stale"
    print(f"[5/5] Financial refresh ({threshold_label}) "
          f"— checking {len(active_members)} members...")

    fin_counts = {"updated": 0, "skipped": 0, "failed": 0}
    fin_failed = []
    sorted_members = sorted(active_members)

    for i, ticker in enumerate(sorted_members, start=1):
        result = "failed"
        try:
            result = _update_financial(ticker, force=force)
            fin_counts[result] += 1
            if result == "failed":
                fin_failed.append(ticker)
            if result == "updated":
                print(f"      [{i}/{len(sorted_members)}] {ticker} — refreshed")
        except Exception as e:
            print(f"      [{ticker}] ERROR: {e}")
            fin_counts["failed"] += 1
            fin_failed.append(ticker)

        # Sleep only when yfinance was actually called.
        if result in ("updated", "failed") and i < len(sorted_members):
            time.sleep(SLEEP_BETWEEN)

    print(f"      → updated={fin_counts['updated']}  "
          f"skipped={fin_counts['skipped']}  "
          f"failed={fin_counts['failed']}")
    if fin_failed:
        print(f"      → Failures: {fin_failed}")
    print()

    # ── Summary ─────────────────────────────────────────────────────────────────
    elapsed    = (datetime.now() - run_start).total_seconds()
    all_failed = sorted(set(backfill_failed + price_failed + fin_failed))

    print(f"{'=' * 60}")
    print(f"  Complete — {elapsed:.0f}s elapsed")
    print(f"{'=' * 60}")
    print(f"  S&P 500 members  : {len(active_members)}")
    print(f"  New additions    : {len(newly_added)}")
    print(f"  Removals         : {len(newly_removed)}")
    print(f"  Prices updated   : {price_counts['updated']}")
    print(f"  Prices skipped   : {price_counts['skipped']}")
    print(f"  Financials done  : {fin_counts['updated']}")
    print(f"  Financials skip  : {fin_counts['skipped']}")
    print(f"  Total failures   : {len(all_failed)}")

    if all_failed:
        print(f"\n  Re-run failed tickers:")
        print(f"  python data/daily_updater.py --ticker {' '.join(all_failed)} --force")

    print(f"{'=' * 60}\n")


# ── Dry-run mode ───────────────────────────────────────────────────────────────

def dry_run() -> None:
    """
    Preview what a full run would do — no data is written.
    Useful for debugging or validating the cron setup.
    """
    print(f"\n{'=' * 60}")
    print(f"  daily_updater — DRY RUN  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  No data will be written.")
    print(f"{'=' * 60}\n")

    print("Fetching S&P 500 list from Wikipedia...")
    sp500_tickers = get_sp500_tickers()
    print(f"  → {len(sp500_tickers)} tickers returned")

    if len(sp500_tickers) < MIN_SP500_COUNT:
        print(f"  WARNING: below floor of {MIN_SP500_COUNT} — a real run would abort here.")

    current_in_db = _get_active_members()
    new_set       = set(sp500_tickers)
    would_add     = new_set - current_in_db
    would_remove  = current_in_db - new_set

    print(f"\nMembership diff (current DB: {len(current_in_db)} active members):")
    print(f"  Would add    ({len(would_add)}):    {sorted(would_add) or 'none'}")
    print(f"  Would remove ({len(would_remove)}): {sorted(would_remove) or 'none'}")

    print(f"\nStaleness check ({len(current_in_db)} current members):")
    price_stale = sum(1 for t in current_in_db if _price_is_stale(t))
    fin_stale   = sum(1 for t in current_in_db if _financial_is_stale(t))
    print(f"  Price stale (< today)          : {price_stale}")
    print(f"  Financial stale (> {FINANCIAL_REFRESH_DAYS}d)        : {fin_stale}")
    print(f"\n  No data written. Remove --dry-run to execute.\n")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Daily S&P 500 data updater. "
            "Normally run by cron after 16:30 EST market close."
        )
    )
    parser.add_argument(
        "--ticker", nargs="+", metavar="TICKER",
        help=(
            "Update specific tickers only (skips membership sync). "
            "Example: --ticker AAPL MSFT NVDA"
        ),
    )
    parser.add_argument(
        "--force", action="store_true",
        help=(
            "Force refresh all data regardless of staleness. "
            "Use after a multi-day outage or a fetcher.py fix."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes (membership diff + staleness counts) without writing anything.",
    )
    args = parser.parse_args()

    # ── Database sanity check ───────────────────────────────────────────────────
    if not test_connection():
        print("[updater] Cannot reach the database. Check DATABASE_URL and retry.")
        sys.exit(1)

    create_tables()

    # ── Dispatch ────────────────────────────────────────────────────────────────
    if args.dry_run:
        dry_run()

    elif args.ticker:
        # Manual mode: update only the specified tickers, no membership sync.
        tickers = [t.upper() for t in args.ticker]
        print(f"\n[updater] Manual mode — {len(tickers)} ticker(s)"
              f"{'  [FORCED]' if args.force else ''}\n")

        for i, ticker in enumerate(tickers, start=1):
            print(f"── [{i}/{len(tickers)}] {ticker}")
            price_r = _update_price(ticker, force=args.force)
            fin_r   = _update_financial(ticker, force=args.force)
            print(f"   price={price_r}  financial={fin_r}")
            if i < len(tickers):
                time.sleep(SLEEP_BETWEEN)

        print("\n[updater] Manual update complete.\n")

    else:
        # Normal cron mode: full pipeline.
        run(force=args.force)
