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


def calculate_all_metrics(ticker):
    """
    Fetch financial data once and compute all metrics in a single pass.
    Also passes through raw fields (pe_ratio, market_cap, etc.) so downstream
    modules like valuation.py and screener.py don't need to re-query the database.

    Returns:
        dict with all computed metrics and raw fields, or None if no data found.

    ── Metric Reference ────────────────────────────────────────────────────────

    Gross Margin = Gross Profit / Revenue
        How much of each revenue dollar remains after direct production costs,
        before operating expenses such as salaries and rent.
        Reflects the width of a company's competitive moat — high gross margin
        usually indicates pricing power or a hard-to-replicate advantage.
        Benchmark: > 40% is strong; software companies often exceed 70%.

    Profit Margin = Net Income / Revenue
        How much of each revenue dollar the company ultimately keeps as profit,
        after all costs including operating expenses, interest, and taxes.
        Read together with gross margin: a high gross margin paired with a low
        profit margin signals that the company is spending heavily on sales,
        R&D, or carries significant debt interest.
        Benchmark: > 20% is strong for most industries.

    ROE (Return on Equity) = Net Income / Shareholders' Equity
        How efficiently the company converts shareholders' capital into profit.
        Answers the question: for every $1 shareholders own in the company,
        how much profit did it generate?
        Note: ROE can be misleading in two edge cases —
          - Extreme buybacks (e.g. AAPL > 100%): heavy repurchases shrink equity,
            inflating ROE arithmetically. This is generally positive for shareholders.
          - Negative equity (e.g. MCD): when total debt exceeds total assets,
            equity turns negative and ROE loses all interpretive meaning.
        Benchmark: > 15% is healthy; elite companies often exceed 30%.

    Debt Ratio = Total Debt / Total Assets
        What proportion of the company's assets are financed by debt.
        Debt is a double-edged amplifier: it magnifies returns in good times
        and accelerates collapse in bad times. High debt ratios are especially
        dangerous during economic downturns when revenue falls but interest
        obligations remain fixed.
        Note: certain industries (banks, insurance, REITs) operate with
        structurally high leverage — this metric is less meaningful for them.
        Benchmark: < 50% is generally considered conservative.

    ────────────────────────────────────────────────────────────────────────────
    """
    data = get_financial_data(ticker)
    if not data:
        return None

    revenue             = data.get('revenue')
    net_income          = data.get('net_income')
    gross_profit        = data.get('gross_profit')
    total_assets        = data.get('total_assets')
    total_debt          = data.get('total_debt')
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
        'pe_ratio':       data.get('pe_ratio'),
        'eps':            data.get('eps'),
        'market_cap':     data.get('market_cap'),
        'free_cash_flow': data.get('free_cash_flow'),
        'revenue':        revenue,
        'net_income':     net_income,
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