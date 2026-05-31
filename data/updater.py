import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ALL_TICKERS
from data.fetcher import get_stock_price, get_financial_data
from data.db import (
    create_tables,
    save_stock_prices,
    save_financial_data,
    get_last_updated,
)


# ─── Constants ────────────────────────────────────────────────────────────────

# Financial data older than this many days will be refreshed
FINANCIAL_REFRESH_DAYS = 90


# ─── Core Logic ───────────────────────────────────────────────────────────────

def _is_price_stale(ticker: str) -> bool:
    """
    Returns True if price data needs to be refreshed.

    Rules:
        - No data exists yet → stale
        - Last update was before today → stale (new trading day)
        - Last update was today → fresh (already fetched today)
    """
    last = get_last_updated(ticker, data_type="price")

    if last is None:
        return True  # No data at all

    last_date = datetime.strptime(last, "%Y-%m-%d").date()
    today     = date.today()

    return last_date < today


def _is_financial_stale(ticker: str) -> bool:
    """
    Returns True if financial data needs to be refreshed.

    Rules:
        - No data exists yet → stale
        - Last update was more than FINANCIAL_REFRESH_DAYS ago → stale
        - Otherwise → fresh
    """
    last = get_last_updated(ticker, data_type="financial")

    if last is None:
        return True

    last_date = datetime.strptime(last, "%Y-%m-%d").date()
    days_old  = (date.today() - last_date).days

    return days_old > FINANCIAL_REFRESH_DAYS


# ─── Public Interface ─────────────────────────────────────────────────────────

def update_ticker(ticker: str, force: bool = False) -> dict:
    """
    Update price and financial data for a single ticker if stale.

    Args:
        ticker: Stock ticker symbol e.g. 'AAPL'
        force:  If True, skip staleness check and always refresh

    Returns a status dict:
        {
            "ticker":    str,
            "price":     "updated" | "skipped" | "failed",
            "financial": "updated" | "skipped" | "failed",
        }
    """
    status = {"ticker": ticker, "price": "skipped", "financial": "skipped"}

    # ── Price data ─────────────────────────────────────────────────────────
    if force or _is_price_stale(ticker):
        df = get_stock_price(ticker)
        if df is not None:
            save_stock_prices(ticker, df)
            status["price"] = "updated"
        else:
            status["price"] = "failed"
    else:
        print(f"[updater] {ticker}: price data is fresh, skipping")

    # ── Financial data ─────────────────────────────────────────────────────
    if force or _is_financial_stale(ticker):
        data = get_financial_data(ticker)
        if data is not None:
            save_financial_data(data)
            status["financial"] = "updated"
        else:
            status["financial"] = "failed"
    else:
        print(f"[updater] {ticker}: financial data is fresh, skipping")

    return status


def update_all(force: bool = False) -> list[dict]:
    """
    Update all tickers defined in config.

    Args:
        force: If True, refresh all data regardless of staleness

    Returns a list of status dicts (one per ticker).
    """
    create_tables()

    print(f"\n[updater] Starting update for {len(ALL_TICKERS)} tickers "
          f"({'forced' if force else 'smart'})\n")

    results = []
    for ticker in ALL_TICKERS:
        print(f"[updater] ── {ticker} ──")
        result = update_ticker(ticker, force=force)
        results.append(result)

    # ── Summary ────────────────────────────────────────────────────────────
    updated = sum(1 for r in results if r["price"] == "updated")
    skipped = sum(1 for r in results if r["price"] == "skipped")
    failed  = sum(1 for r in results if r["price"] == "failed")

    print(f"\n[updater] Done — "
          f"updated: {updated}, skipped: {skipped}, failed: {failed}")

    return results