# analysis/metrics.py
# Computes financial metrics from stored fundamental data.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db import get_financial_data


def _safe_divide(numerator, denominator):
    """Return numerator / denominator. Return None if either input is None or denominator is 0."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def calculate_profit_margin(ticker):
    """
    Profit Margin = Net Income / Revenue

    How much of each revenue dollar the company keeps as profit.
    Good benchmark: > 20% is strong for most industries.
    """
    data = get_financial_data(ticker)
    if not data:
        return None
    return _safe_divide(data.get('net_income'), data.get('revenue'))


def calculate_roe(ticker):
    """
    Return on Equity (ROE) = Net Income / Shareholders Equity

    How efficiently the company turns shareholder capital into profit.
    Good benchmark: > 15% is healthy; Apple consistently exceeds 100%.
    """
    data = get_financial_data(ticker)
    if not data:
        return None
    return _safe_divide(data.get('net_income'), data.get('shareholders_equity'))


def calculate_debt_ratio(ticker):
    """
    Debt Ratio = Total Debt / Total Assets

    What proportion of assets is financed by debt.
    Good benchmark: < 50% is generally considered conservative.
    """
    data = get_financial_data(ticker)
    if not data:
        return None
    return _safe_divide(data.get('total_debt'), data.get('total_assets'))


def calculate_gross_margin(ticker):
    """
    Gross Margin = Gross Profit / Revenue

    Profitability after direct costs only (before operating expenses).
    Good benchmark: > 40% is strong; software companies often exceed 70%.
    """
    data = get_financial_data(ticker)
    if not data:
        return None
    return _safe_divide(data.get('gross_profit'), data.get('revenue'))


def calculate_all_metrics(ticker):
    """
    Fetch financial data once and compute all metrics in a single pass.

    Also passes through raw fields (pe_ratio, market_cap, etc.) so downstream
    modules like valuation.py and screener.py don't need to re-query the database.

    Returns:
        dict with all computed metrics and raw fields, or None if no data found.
    """
    data = get_financial_data(ticker)
    if not data:
        return None

    revenue            = data.get('revenue')
    net_income         = data.get('net_income')
    gross_profit       = data.get('gross_profit')
    total_assets       = data.get('total_assets')
    total_debt         = data.get('total_debt')
    shareholders_equity = data.get('shareholders_equity')

    return {
        # Identity
        'ticker': ticker,

        # Computed metrics
        'profit_margin': _safe_divide(net_income, revenue),
        'roe':           _safe_divide(net_income, shareholders_equity),
        'debt_ratio':    _safe_divide(total_debt, total_assets),
        'gross_margin':  _safe_divide(gross_profit, revenue),

        # Raw fields passed through for downstream use
        'pe_ratio':      data.get('pe_ratio'),
        'eps':           data.get('eps'),
        'market_cap':    data.get('market_cap'),
        'free_cash_flow': data.get('free_cash_flow'),
        'revenue':       revenue,
        'net_income':    net_income,
    }


if __name__ == '__main__':
    test_tickers = ['AAPL', 'MSFT', 'GOOGL']

    for ticker in test_tickers:
        metrics = calculate_all_metrics(ticker)
        if metrics:
            print(f"\n{ticker}")
            print(f"  Profit Margin : {metrics['profit_margin']:.2%}")
            print(f"  ROE           : {metrics['roe']:.2%}")
            print(f"  Debt Ratio    : {metrics['debt_ratio']:.2%}")
            print(f"  Gross Margin  : {metrics['gross_margin']:.2%}")
        else:
            print(f"\n{ticker}: no data available")