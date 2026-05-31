# config.py
# Central configuration for the stock screener.
# All paths, constants, and stock lists are defined here.

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'stocks.db')

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------

APP_TITLE = 'US Stock Screener & Valuation'
APP_ICON  = '📈'

# ---------------------------------------------------------------------------
# Data settings
# ---------------------------------------------------------------------------

HISTORICAL_DAYS = 365          # Days of price history to fetch
FINANCIAL_REFRESH_DAYS = 90   # Days before financial data is considered stale

# ---------------------------------------------------------------------------
# Stock universe — 11 GICS sectors, top 10 by market cap per sector
# Source: FactSet via Charles Schwab, as of February 2026
# ---------------------------------------------------------------------------

STOCKS = {
    # Overall top 10 by market cap across all sectors
    'Default List': [
        'NVDA', 'GOOGL', 'AAPL', 'MSFT', 'AMZN',
        'AVGO', 'META', 'TSLA', 'BRK-B', 'LLY',
    ],

    # GICS Sector 1: Information Technology
    'Information Technology': [
        'NVDA', 'AAPL', 'MSFT', 'AVGO', 'ORCL',
        'CRM', 'ACN', 'AMD', 'CSCO', 'IBM',
    ],

    # GICS Sector 2: Communication Services
    'Communication Services': [
        'GOOGL', 'META', 'NFLX', 'TMUS', 'VZ',
        'T', 'DIS', 'CMCSA', 'SPOT', 'WBD',
    ],

    # GICS Sector 3: Consumer Discretionary
    'Consumer Discretionary': [
        'AMZN', 'TSLA', 'HD', 'MCD', 'TJX',
        'LOW', 'BKNG', 'SBUX', 'MAR', 'NKE',
    ],

    # GICS Sector 4: Consumer Staples
    'Consumer Staples': [
        'WMT', 'COST', 'PG', 'KO', 'PM',
        'PEP', 'MO', 'MDLZ', 'MNST', 'CL',
    ],

    # GICS Sector 5: Health Care
    'Health Care': [
        'LLY', 'JNJ', 'ABBV', 'MRK', 'UNH',
        'ABT', 'AMGN', 'GILD', 'TMO', 'ISRG',
    ],

    # GICS Sector 6: Financials
    'Financials': [
        'BRK-B', 'JPM', 'BAC', 'GS', 'MS',
        'WFC', 'AXP', 'C', 'BLK', 'COF',
    ],

    # GICS Sector 7: Industrials
    'Industrials': [
        'GE', 'RTX', 'CAT', 'UPS', 'HON',
        'LMT', 'DE', 'UNP', 'ETN', 'BA',
    ],

    # GICS Sector 8: Energy
    'Energy': [
        'XOM', 'CVX', 'COP', 'WMB', 'SLB',
        'KMI', 'EOG', 'PSX', 'VLO', 'BKR',
    ],

    # GICS Sector 9: Materials
    'Materials': [
        'LIN', 'SHW', 'APD', 'ECL', 'FCX',
        'NEM', 'NUE', 'PPG', 'VMC', 'MLM',
    ],

    # GICS Sector 10: Real Estate
    'Real Estate': [
        'AMT', 'PLD', 'EQIX', 'CCI', 'PSA',
        'WELL', 'O', 'DLR', 'AVB', 'EQR',
    ],

    # GICS Sector 11: Utilities
    'Utilities': [
        'NEE', 'SO', 'DUK', 'AEP', 'EXC',
        'SRE', 'XEL', 'PCG', 'ED', 'ETR',
    ],
}

# Flat list of all unique tickers across all groups
ALL_TICKERS = list(dict.fromkeys(
    ticker for tickers in STOCKS.values() for ticker in tickers
))

# ---------------------------------------------------------------------------
# Screener defaults
# ---------------------------------------------------------------------------

SCREEN_DEFAULTS = {
    'min_score':         0,
    'max_pe':            500,
    'min_roe':           -1.0,
    'max_debt_ratio':    1.0,
    'min_profit_margin': -1.0,
}

DEFAULT_SORT_BY        = 'score'
DEFAULT_SORT_ASCENDING = False