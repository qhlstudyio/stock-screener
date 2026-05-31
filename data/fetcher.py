import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add project root to path so config can be imported from any working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import HISTORICAL_DAYS, ALL_TICKERS


# ─── Price Data ───────────────────────────────────────────────────────────────

def get_stock_price(ticker: str) -> pd.DataFrame | None:
    """
    Fetch historical daily price data for a stock.

    Returns a DataFrame with columns:
        date, open, high, low, close, volume

    Returns None if data cannot be fetched.
    """
    try:
        end_date   = datetime.today()
        start_date = end_date - timedelta(days=HISTORICAL_DAYS)

        stock = yf.Ticker(ticker)
        df    = stock.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d")
        )

        if df.empty:
            print(f"[fetcher] No price data found for {ticker}")
            return None

        # Reset index so Date becomes a regular column
        df = df.reset_index()

        # Keep only the columns we need
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

        # Lowercase column names for consistency across the project
        df.columns = [col.lower() for col in df.columns]

        # Remove timezone info — SQLite does not support timezone-aware datetimes
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

        print(f"[fetcher] {ticker}: fetched {len(df)} days of price data")
        return df

    except Exception as e:
        print(f"[fetcher] Error fetching price data for {ticker}: {e}")
        return None


# ─── Financial Data ───────────────────────────────────────────────────────────

def get_financial_data(ticker: str) -> dict | None:
    """
    Fetch key financial data for a stock.

    Returns a dict with:
        market_cap, pe_ratio, eps
        revenue, net_income, gross_profit
        total_assets, total_debt, shareholders_equity
        free_cash_flow
        fetched_at (ISO timestamp)

    Returns None if data cannot be fetched.
    """
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        if not info or info.get("regularMarketPrice") is None:
            print(f"[fetcher] No info data found for {ticker}")
            return None

        # ── Market data (from .info) ───────────────────────────────────────
        market_cap = info.get("marketCap")
        pe_ratio   = info.get("trailingPE")
        eps        = info.get("trailingEps")

        # ── Income statement ───────────────────────────────────────────────
        # .financials: rows = line items, columns = fiscal years (newest first)
        revenue      = None
        net_income   = None
        gross_profit = None

        try:
            financials = stock.financials
            if financials is not None and not financials.empty:
                latest       = financials.iloc[:, 0]   # Most recent fiscal year
                revenue      = _safe_get(latest, "Total Revenue")
                net_income   = _safe_get(latest, "Net Income")
                gross_profit = _safe_get(latest, "Gross Profit")
        except Exception as e:
            print(f"[fetcher] {ticker}: could not parse income statement — {e}")

        # ── Balance sheet ──────────────────────────────────────────────────
        total_assets        = None
        total_debt          = None
        shareholders_equity = None

        try:
            balance_sheet = stock.balance_sheet
            if balance_sheet is not None and not balance_sheet.empty:
                latest              = balance_sheet.iloc[:, 0]
                total_assets        = _safe_get(latest, "Total Assets")
                total_debt          = _safe_get(latest, "Total Debt")
                shareholders_equity = _safe_get(latest, "Stockholders Equity")
        except Exception as e:
            print(f"[fetcher] {ticker}: could not parse balance sheet — {e}")

        # ── Cash flow statement ────────────────────────────────────────────
        free_cash_flow = None

        try:
            cashflow = stock.cashflow
            if cashflow is not None and not cashflow.empty:
                latest         = cashflow.iloc[:, 0]
                free_cash_flow = _safe_get(latest, "Free Cash Flow")
        except Exception as e:
            print(f"[fetcher] {ticker}: could not parse cash flow — {e}")

        result = {
            "ticker":               ticker,
            "market_cap":           market_cap,
            "pe_ratio":             pe_ratio,
            "eps":                  eps,
            "revenue":              revenue,
            "net_income":           net_income,
            "gross_profit":         gross_profit,
            "total_assets":         total_assets,
            "total_debt":           total_debt,
            "shareholders_equity":  shareholders_equity,
            "free_cash_flow":       free_cash_flow,
            "fetched_at":           datetime.now().isoformat(),
        }

        print(f"[fetcher] {ticker}: financial data fetched successfully")
        return result

    except Exception as e:
        print(f"[fetcher] Error fetching financial data for {ticker}: {e}")
        return None


# ─── Batch Fetch ──────────────────────────────────────────────────────────────

def fetch_all_stocks() -> dict:
    """
    Fetch price and financial data for all tickers defined in config.

    Returns a dict:
        {
            "AAPL": {
                "price":    DataFrame | None,
                "financial": dict | None
            },
            ...
        }
    """
    results = {}

    for ticker in ALL_TICKERS:
        print(f"\n[fetcher] ── Fetching {ticker} ──")
        results[ticker] = {
            "price":     get_stock_price(ticker),
            "financial": get_financial_data(ticker),
        }

    print(f"\n[fetcher] Done. Fetched {len(results)} stocks.")
    return results


# ─── Internal Helper ──────────────────────────────────────────────────────────

def _safe_get(series: pd.Series, key: str) -> float | None:
    """
    Safely retrieve a value from a pandas Series.
    Returns None if the key doesn't exist or the value is NaN.
    """
    try:
        value = series.get(key)
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None