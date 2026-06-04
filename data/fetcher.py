# data/fetcher.py
# Fetches price and financial data from yfinance.
# Called only by bootstrap.py and daily_updater.py — never by the user-facing API.
#
# Design principles:
#   - Only raw data is returned. No ratios, no derived metrics.
#   - All computation happens in the analysis layer (metrics.py, valuation.py).
#   - Every function returns None (or empty list) on failure, never raises.

from datetime import datetime, timedelta
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests


# ── Internal helper ────────────────────────────────────────────────────────────

def _safe_get(series: pd.Series, key: str) -> float | None:
    """
    Safely retrieve a numeric value from a pandas Series by row label.
    Returns None if the key does not exist or the value is NaN/non-numeric.
    """
    try:
        value = series.get(key)
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _to_period_annual(ts) -> str:
    """Convert a Timestamp to an annual period string: '2024'"""
    return str(pd.Timestamp(ts).year)


def _to_period_quarterly(ts) -> str:
    """Convert a Timestamp to a quarterly period string: '2024Q4'"""
    t       = pd.Timestamp(ts)
    quarter = (t.month - 1) // 3 + 1
    return f"{t.year}Q{quarter}"


# ── Price data ─────────────────────────────────────────────────────────────────

def get_stock_price(ticker: str, days: int = 365) -> pd.DataFrame | None:
    """
    Fetch historical daily OHLCV data for a single ticker.

    Parameters
    ----------
    ticker : stock ticker symbol (e.g. 'AAPL', 'SPY')
    days   : number of calendar days of history to fetch (default 365)
             bootstrap.py passes 5 * 365 for the initial 5-year load.

    Returns
    -------
    DataFrame with columns: date, open, high, low, close, volume
    Returns None if data cannot be fetched or is empty.
    """
    import yfinance as yf

    try:
        end_date   = datetime.today()
        start_date = end_date - timedelta(days=days)

        stock = yf.Ticker(ticker)
        df    = stock.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
        )

        if df is None or df.empty:
            print(f"[fetcher] {ticker}: no price data returned")
            return None

        df = df.reset_index()
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        df.columns = ["date", "open", "high", "low", "close", "volume"]

        # Strip timezone so SQLite/PostgreSQL accept the values without conversion
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

        print(f"[fetcher] {ticker}: {len(df)} price rows fetched")
        return df

    except Exception as e:
        print(f"[fetcher] {ticker}: error fetching price data — {e}")
        return None


# ── Financial snapshot ─────────────────────────────────────────────────────────

def get_financial_data(ticker: str) -> dict | None:
    """
    Fetch the latest financial snapshot for a single ticker.

    Pulls from three yfinance sources in one call:
      - stock.info          → identity, market data, analyst consensus
      - stock.financials    → income statement (most recent annual period)
      - stock.balance_sheet → balance sheet  (most recent annual period)
      - stock.cashflow      → cash flow      (most recent annual period)

    Returns a flat dict whose keys match the financial_data table columns.
    Returns None if essential data (market cap, price) is unavailable.
    """
    import yfinance as yf

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        # A missing regularMarketPrice means yfinance has no usable data
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            print(f"[fetcher] {ticker}: no market data in stock.info")
            return None

        # ── Identity ───────────────────────────────────────────────────────────
        company_name = info.get("longName") or info.get("shortName")
        exchange     = info.get("exchange")
        sector       = info.get("sector")
        industry     = info.get("industry")

        # ── Share data ─────────────────────────────────────────────────────────
        shares_outstanding = info.get("sharesOutstanding")

        # ── Market pricing ─────────────────────────────────────────────────────
        market_cap       = info.get("marketCap")
        enterprise_value = info.get("enterpriseValue")
        ev_ebitda        = info.get("enterpriseToEbitda")
        ev_revenue       = info.get("enterpriseToRevenue")
        pe_ratio         = info.get("trailingPE")
        forward_pe       = info.get("forwardPE")
        eps              = info.get("trailingEps")
        forward_eps      = info.get("forwardEps")

        # ── Income statement ───────────────────────────────────────────────────
        revenue              = None
        net_income           = None
        gross_profit         = None
        operating_income     = None
        research_development = None
        interest_expense     = None

        try:
            fin = stock.financials
            if fin is not None and not fin.empty:
                latest               = fin.iloc[:, 0]
                revenue              = _safe_get(latest, "Total Revenue")
                net_income           = _safe_get(latest, "Net Income")
                gross_profit         = _safe_get(latest, "Gross Profit")
                operating_income     = _safe_get(latest, "Operating Income")
                research_development = _safe_get(latest, "Research And Development")
                interest_expense     = _safe_get(latest, "Interest Expense")
        except Exception as e:
            print(f"[fetcher] {ticker}: income statement error — {e}")

        # ── Balance sheet ──────────────────────────────────────────────────────
        total_assets        = None
        total_debt          = None
        shareholders_equity = None
        current_assets      = None
        current_liabilities = None
        cash_and_equivalents = None

        try:
            bs = stock.balance_sheet
            if bs is not None and not bs.empty:
                latest               = bs.iloc[:, 0]
                total_assets         = _safe_get(latest, "Total Assets")
                total_debt           = _safe_get(latest, "Total Debt")
                shareholders_equity  = _safe_get(latest, "Stockholders Equity")
                current_assets       = _safe_get(latest, "Current Assets")
                current_liabilities  = _safe_get(latest, "Current Liabilities")
                cash_and_equivalents = (
                    _safe_get(latest, "Cash And Cash Equivalents") or
                    _safe_get(latest, "Cash Cash Equivalents And Short Term Investments")
                )
        except Exception as e:
            print(f"[fetcher] {ticker}: balance sheet error — {e}")

        # ── Cash flow ──────────────────────────────────────────────────────────
        free_cash_flow       = None
        capital_expenditures = None

        try:
            cf = stock.cashflow
            if cf is not None and not cf.empty:
                latest               = cf.iloc[:, 0]
                free_cash_flow       = _safe_get(latest, "Free Cash Flow")
                capital_expenditures = _safe_get(latest, "Capital Expenditure")
        except Exception as e:
            print(f"[fetcher] {ticker}: cash flow error — {e}")

        # ── Dividends ──────────────────────────────────────────────────────────
        dividend_yield = info.get("dividendYield")
        dividend_rate  = info.get("dividendRate")
        payout_ratio   = info.get("payoutRatio")

        # ── Risk ───────────────────────────────────────────────────────────────
        beta = info.get("beta")

        # ── Workforce ──────────────────────────────────────────────────────────
        full_time_employees = info.get("fullTimeEmployees")

        # ── Analyst consensus ──────────────────────────────────────────────────
        target_mean_price  = info.get("targetMeanPrice")
        target_high_price  = info.get("targetHighPrice")
        target_low_price   = info.get("targetLowPrice")
        analyst_count      = info.get("numberOfAnalystOpinions")
        recommendation_key = info.get("recommendationKey")

        result = {
            "ticker":               ticker,
            "company_name":         company_name,
            "exchange":             exchange,
            "sector":               sector,
            "industry":             industry,
            "shares_outstanding":   shares_outstanding,
            "market_cap":           market_cap,
            "enterprise_value":     enterprise_value,
            "ev_ebitda":            ev_ebitda,
            "ev_revenue":           ev_revenue,
            "pe_ratio":             pe_ratio,
            "forward_pe":           forward_pe,
            "eps":                  eps,
            "forward_eps":          forward_eps,
            "revenue":              revenue,
            "net_income":           net_income,
            "gross_profit":         gross_profit,
            "operating_income":     operating_income,
            "research_development": research_development,
            "interest_expense":     interest_expense,
            "total_assets":         total_assets,
            "total_debt":           total_debt,
            "shareholders_equity":  shareholders_equity,
            "current_assets":       current_assets,
            "current_liabilities":  current_liabilities,
            "cash_and_equivalents": cash_and_equivalents,
            "free_cash_flow":       free_cash_flow,
            "capital_expenditures": capital_expenditures,
            "dividend_yield":       dividend_yield,
            "dividend_rate":        dividend_rate,
            "payout_ratio":         payout_ratio,
            "beta":                 beta,
            "full_time_employees":  full_time_employees,
            "target_mean_price":    target_mean_price,
            "target_high_price":    target_high_price,
            "target_low_price":     target_low_price,
            "analyst_count":        analyst_count,
            "recommendation_key":   recommendation_key,
            "fetched_at":           datetime.now().isoformat(),
        }

        print(f"[fetcher] {ticker}: financial snapshot fetched")
        return result

    except Exception as e:
        print(f"[fetcher] {ticker}: error fetching financial data — {e}")
        return None


# ── Financial history ──────────────────────────────────────────────────────────

def get_financial_history(ticker: str) -> list[dict]:
    """
    Fetch multi-period financial history for a single ticker.

    Collects both annual and quarterly data from four yfinance statements:
      - stock.financials              (annual income statement)
      - stock.quarterly_financials    (quarterly income statement)
      - stock.balance_sheet           (annual balance sheet)
      - stock.quarterly_balance_sheet (quarterly balance sheet)
      - stock.cashflow                (annual cash flow)
      - stock.quarterly_cashflow      (quarterly cash flow)

    Each period is returned as a flat dict matching the financial_history
    table columns. Annual and quarterly records are kept separate via
    the period_type field ('annual' | 'quarterly').

    Period format:
      annual    → '2024', '2023', '2022', ...
      quarterly → '2024Q4', '2024Q3', ...

    Returns a list of dicts (may be empty if no data is available).
    """
    import yfinance as yf

    records = []
    now     = datetime.now().isoformat()

    try:
        stock = yf.Ticker(ticker)
    except Exception as e:
        print(f"[fetcher] {ticker}: could not create Ticker object — {e}")
        return records

    # Helper: merge one statement's columns into the running period dict
    def _extract_statement(statement, period_type: str, period_fn) -> dict:
        """
        Parse a yfinance financial statement DataFrame into a dict of dicts,
        keyed by period string. Returns {} on failure.
        """
        result = {}
        if statement is None or statement.empty:
            return result
        try:
            for col in statement.columns:
                period = period_fn(col)
                if period not in result:
                    result[period] = {"period": period, "period_type": period_type}
                row = statement[col]
                result[period]["revenue"]             = _safe_get(row, "Total Revenue")
                result[period]["net_income"]          = _safe_get(row, "Net Income")
                result[period]["gross_profit"]        = _safe_get(row, "Gross Profit")
                result[period]["operating_income"]    = _safe_get(row, "Operating Income")
        except Exception as e:
            print(f"[fetcher] {ticker}: statement parse error ({period_type}) — {e}")
        return result

    def _extract_balance(statement, period_type: str, period_fn, periods: dict) -> None:
        """Merge balance sheet fields into an existing periods dict in place."""
        if statement is None or statement.empty:
            return
        try:
            for col in statement.columns:
                period = period_fn(col)
                if period not in periods:
                    periods[period] = {"period": period, "period_type": period_type}
                row = statement[col]
                periods[period]["total_assets"]        = _safe_get(row, "Total Assets")
                periods[period]["total_debt"]          = _safe_get(row, "Total Debt")
                periods[period]["shareholders_equity"] = _safe_get(row, "Stockholders Equity")
        except Exception as e:
            print(f"[fetcher] {ticker}: balance sheet parse error ({period_type}) — {e}")

    def _extract_cashflow(statement, period_type: str, period_fn, periods: dict) -> None:
        """Merge cash flow fields into an existing periods dict in place."""
        if statement is None or statement.empty:
            return
        try:
            for col in statement.columns:
                period = period_fn(col)
                if period not in periods:
                    periods[period] = {"period": period, "period_type": period_type}
                row = statement[col]
                periods[period]["free_cash_flow"] = _safe_get(row, "Free Cash Flow")
        except Exception as e:
            print(f"[fetcher] {ticker}: cash flow parse error ({period_type}) — {e}")

    # ── Annual ─────────────────────────────────────────────────────────────────
    annual = _extract_statement(
        stock.financials, "annual", _to_period_annual
    )
    _extract_balance(
        stock.balance_sheet, "annual", _to_period_annual, annual
    )
    _extract_cashflow(
        stock.cashflow, "annual", _to_period_annual, annual
    )

    # ── Quarterly ──────────────────────────────────────────────────────────────
    quarterly = _extract_statement(
        stock.quarterly_financials, "quarterly", _to_period_quarterly
    )
    _extract_balance(
        stock.quarterly_balance_sheet, "quarterly", _to_period_quarterly, quarterly
    )
    _extract_cashflow(
        stock.quarterly_cashflow, "quarterly", _to_period_quarterly, quarterly
    )

    # ── Assemble final record list ─────────────────────────────────────────────
    for period_dict in (annual, quarterly):
        for period_data in period_dict.values():
            record = {
                "ticker":               ticker,
                "period":               period_data.get("period"),
                "period_type":          period_data.get("period_type"),
                "revenue":              period_data.get("revenue"),
                "net_income":           period_data.get("net_income"),
                "gross_profit":         period_data.get("gross_profit"),
                "operating_income":     period_data.get("operating_income"),
                "free_cash_flow":       period_data.get("free_cash_flow"),
                "total_assets":         period_data.get("total_assets"),
                "total_debt":           period_data.get("total_debt"),
                "shareholders_equity":  period_data.get("shareholders_equity"),
                "fetched_at":           now,
            }
            records.append(record)

    print(f"[fetcher] {ticker}: {len(records)} history records assembled "
          f"({len(annual)} annual, {len(quarterly)} quarterly)")
    return records


# ── S&P 500 membership ─────────────────────────────────────────────────────────

def get_sp500_tickers() -> list[str]:
    """
    Fetch the current S&P 500 constituent list from Wikipedia.

    Uses a browser-like User-Agent header to avoid 403 rejections.
    requests is not an extra dependency — yfinance already requires it.

    Returns a list of ticker symbols (dots replaced with hyphens to match
    yfinance convention, e.g. 'BRK.B' → 'BRK-B').
    Returns an empty list if the fetch fails.
    """
    url     = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        # 核心修改点：使用 io.StringIO(response.text) 代替原有的 response.text
        tables = pd.read_html(io.StringIO(response.text), header=0)
        df = None
        for table in tables:
            if "Symbol" in table.columns:
                df = table
                break

        if df is None:
            cols = [list(t.columns) for t in tables]
            print(f"[fetcher] S&P 500: 'Symbol' column not found. "
                  f"Found {len(tables)} tables with columns: {cols}")
            return []

        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        print(f"[fetcher] S&P 500: {len(tickers)} tickers fetched from Wikipedia")
        return tickers

    except Exception as e:
        print(f"[fetcher] S&P 500: failed to fetch ticker list — {e}")
        return []


# ── Test block ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    TEST_TICKER = "MSFT"
    all_passed  = True

    print("=" * 60)
    print(f"fetcher.py — test run  ({TEST_TICKER})")
    print("=" * 60)

    # Test 1: price data
    print(f"\n[Test 1] get_stock_price('{TEST_TICKER}', days=30)")
    df = get_stock_price(TEST_TICKER, days=30)
    if df is not None and not df.empty:
        print(f"  rows     : {len(df)}")
        print(f"  columns  : {df.columns.tolist()}")
        print(f"  date range: {df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()}")
        print("  PASS ✅")
    else:
        print("  FAIL ❌ — no price data")
        all_passed = False

    # Test 2: financial snapshot
    print(f"\n[Test 2] get_financial_data('{TEST_TICKER}')")
    fd = get_financial_data(TEST_TICKER)
    if fd:
        # Print a representative sample of each category
        checks = [
            ("company_name",       fd.get("company_name")),
            ("exchange",           fd.get("exchange")),
            ("sector",             fd.get("sector")),
            ("shares_outstanding", fd.get("shares_outstanding")),
            ("market_cap",         fd.get("market_cap")),
            ("enterprise_value",   fd.get("enterprise_value")),
            ("ev_ebitda",          fd.get("ev_ebitda")),
            ("pe_ratio",           fd.get("pe_ratio")),
            ("forward_pe",         fd.get("forward_pe")),
            ("revenue",            fd.get("revenue")),
            ("operating_income",   fd.get("operating_income")),
            ("interest_expense",   fd.get("interest_expense")),
            ("current_assets",     fd.get("current_assets")),
            ("current_liabilities",fd.get("current_liabilities")),
            ("cash_and_equivalents",fd.get("cash_and_equivalents")),
            ("free_cash_flow",     fd.get("free_cash_flow")),
            ("capital_expenditures",fd.get("capital_expenditures")),
            ("dividend_yield",     fd.get("dividend_yield")),
            ("dividend_rate",      fd.get("dividend_rate")),
            ("beta",               fd.get("beta")),
            ("target_mean_price",  fd.get("target_mean_price")),
            ("target_high_price",  fd.get("target_high_price")),
            ("target_low_price",   fd.get("target_low_price")),
            ("recommendation_key", fd.get("recommendation_key")),
        ]
        for key, val in checks:
            status = "✅" if val is not None else "⚠️  None"
            print(f"  {key:<25} {status}  {val if val is not None else ''}")
        print("  PASS ✅")
    else:
        print("  FAIL ❌ — returned None")
        all_passed = False

    # Test 3: financial history
    print(f"\n[Test 3] get_financial_history('{TEST_TICKER}')")
    history = get_financial_history(TEST_TICKER)
    if history:
        annual_recs    = [r for r in history if r["period_type"] == "annual"]
        quarterly_recs = [r for r in history if r["period_type"] == "quarterly"]
        print(f"  annual records    : {len(annual_recs)}")
        print(f"  quarterly records : {len(quarterly_recs)}")
        if annual_recs:
            sample = annual_recs[0]
            print(f"  sample annual [{sample['period']}]:")
            for k in ["revenue", "net_income", "gross_profit", "free_cash_flow"]:
                print(f"    {k:<20} {sample.get(k)}")
        print("  PASS ✅")
    else:
        print("  FAIL ❌ — no history records")
        all_passed = False

    # Test 4: S&P 500 ticker list
    print("\n[Test 4] get_sp500_tickers()")
    sp500 = get_sp500_tickers()
    if sp500 and len(sp500) > 490:
        print(f"  count  : {len(sp500)}")
        print(f"  sample : {sp500[:5]}")
        print("  PASS ✅")
    else:
        print(f"  FAIL ❌ — got {len(sp500)} tickers (expected ~503)")
        all_passed = False

    print(f"\n{'=' * 60}")
    print(f"  Result: {'ALL TESTS PASSED ✅' if all_passed else 'SOME TESTS FAILED ❌'}")
    print(f"{'=' * 60}\n")