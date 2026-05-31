import os

# ─── Project Root ─────────────────────────────────────────────────────────────
# Absolute path of the project root directory
# Ensures all paths work correctly regardless of where the script is run from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Database ─────────────────────────────────────────────────────────────────
# Using os.path.join ensures the path works on both Windows and Linux (Streamlit Cloud)
DB_PATH = os.path.join(BASE_DIR, "data", "stocks.db")

# ─── Stock Universe ───────────────────────────────────────────────────────────
# Default stock list organized by sector
# Can be modified here directly, or adjusted by the user through the UI
STOCKS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
    "Healthcare": ["JNJ", "PFE", "UNH"],
    "Consumer":   ["KO", "MCD", "WMT"],
}

# Flat list of all tickers (used when sector grouping is not needed)
ALL_TICKERS = [ticker for sector in STOCKS.values() for ticker in sector]

# ─── Data Fetch Settings ──────────────────────────────────────────────────────
# Number of days of historical price data to fetch per stock
HISTORICAL_DAYS = 365

# ─── Screening Criteria Defaults ──────────────────────────────────────────────
# Default filter values shown in the Streamlit sidebar
# Users can adjust these at runtime without touching this file
SCREEN_DEFAULTS = {
    "pe_max":          30,    # P/E ratio upper limit
    "roe_min":         0.15,  # ROE lower limit (15%)
    "debt_ratio_max":  0.50,  # Debt ratio upper limit (50%)
}

# ─── Streamlit UI Settings ────────────────────────────────────────────────────
APP_TITLE = "US Stock Screener & Valuation"
APP_ICON  = "📈"

# Default column to sort the stock table by
DEFAULT_SORT_BY        = "pe_ratio"
DEFAULT_SORT_ASCENDING = True