# analysis/edge_cases.py
# Rule-based anomaly detection for financial metrics.
#
# Purpose:
#   Identify situations where a metric is mathematically valid but
#   contextually misleading. Returns structured flags used by the frontend
#   to display yellow warning boxes on the individual stock dashboard.
#
# Design principles:
#   - Pure function: takes a metrics dict, returns a list of flags.
#   - No database queries. Caller (screener.py) passes the metrics dict.
#   - No AI. All rules are explicit, deterministic, and documented.
#   - Non-blocking: flags add context, they never override or hide data.
#
# Integration:
#   Called from screener.build_stock_profile() after calculate_all_metrics().
#   Flags are stored in profile['edge_case_flags'] as a list of dicts.
#
# Flag structure:
#   {
#     'code':     str   — machine-readable identifier (stable, used by frontend)
#     'severity': str   — 'warning' | 'info'
#     'metric':   str   — which metric triggered this flag
#     'title':    str   — short label for the UI badge
#     'message':  str   — user-facing explanation (1-2 sentences)
#   }


import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Sector groupings ───────────────────────────────────────────────────────────

# Sectors where high financial leverage is structurally normal and expected.
# Debt ratio thresholds should not be applied cross-sector to these.
HIGH_LEVERAGE_SECTORS = {
    'Financial Services',
    'Financials',
    'Real Estate',
}

# Sectors where negative or zero R&D is normal (not a gap in the data).
NO_RD_SECTORS = {
    'Energy',
    'Consumer Staples',
    'Utilities',
    'Real Estate',
    'Financials',
    'Financial Services',
}


# ── Helper ─────────────────────────────────────────────────────────────────────

def _flag(code, severity, metric, title, message):
    return {
        'code':     code,
        'severity': severity,
        'metric':   metric,
        'title':    title,
        'message':  message,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def check(metrics: dict) -> list[dict]:
    """
    Evaluate a metrics dict and return a list of edge case flags.

    Parameters
    ----------
    metrics : dict returned by calculate_all_metrics(ticker)

    Returns
    -------
    List of flag dicts (may be empty). Order: most severe first.
    """
    flags   = []
    sector  = metrics.get('sector') or ''

    # ── Equity & ROE ──────────────────────────────────────────────────────────

    equity = metrics.get('shareholders_equity')
    roe    = metrics.get('roe')

    if equity is not None and equity < 0:
        flags.append(_flag(
            code     = 'negative_equity',
            severity = 'warning',
            metric   = 'roe',
            title    = 'Negative Equity',
            message  = (
                "Shareholders' equity is negative, making ROE and D/E ratio "
                "mathematically meaningless. This typically results from large "
                "acquisitions (goodwill exceeding equity) or sustained losses. "
                "Evaluate debt levels and cash flow directly."
            ),
        ))

    elif roe is not None and roe > 1.0 and (equity is not None and equity > 0):
        flags.append(_flag(
            code     = 'buyback_inflated_roe',
            severity = 'info',
            metric   = 'roe',
            title    = 'Buyback-Inflated ROE',
            message  = (
                f"ROE exceeds 100% ({roe:.0%}), likely driven by aggressive "
                "share buybacks that have shrunk shareholders' equity. "
                "This is generally a shareholder-friendly capital allocation "
                "decision, not a red flag."
            ),
        ))

    # ── P/E ratio ─────────────────────────────────────────────────────────────

    pe_ratio    = metrics.get('pe_ratio')
    forward_pe  = metrics.get('forward_pe')

    if pe_ratio is not None and pe_ratio > 100:
        flags.append(_flag(
            code     = 'extreme_pe',
            severity = 'info',
            metric   = 'pe_ratio',
            title    = 'Extreme P/E Ratio',
            message  = (
                f"Trailing P/E of {pe_ratio:.0f}x reflects very high growth "
                "expectations, or may be temporarily depressed by one-time "
                "charges or large non-cash amortization. "
                + (
                    f"Forward P/E of {forward_pe:.1f}x suggests analysts "
                    "expect significant earnings improvement."
                    if forward_pe is not None and forward_pe < pe_ratio * 0.5
                    else
                    "Check whether earnings are distorted by non-recurring items."
                )
            ),
        ))

    # ── Payout ratio ──────────────────────────────────────────────────────────

    payout_ratio   = metrics.get('payout_ratio')
    dividend_yield = metrics.get('dividend_yield')
    fcf_margin     = metrics.get('fcf_margin')

    if payout_ratio is not None and payout_ratio > 1.0 and dividend_yield:
        flags.append(_flag(
            code     = 'unsustainable_payout',
            severity = 'warning',
            metric   = 'payout_ratio',
            title    = 'Payout Ratio > 100%',
            message  = (
                f"The company is paying out {payout_ratio:.0%} of net income "
                "as dividends — more than it earns. "
                + (
                    "However, FCF margin is strong, suggesting cash generation "
                    "is healthy despite the accounting payout ratio. "
                    "This often occurs when large non-cash charges (amortization) "
                    "depress reported earnings."
                    if fcf_margin is not None and fcf_margin > 0.10
                    else
                    "Verify that free cash flow is sufficient to sustain the dividend."
                )
            ),
        ))

    # ── FCF quality ───────────────────────────────────────────────────────────

    fcf_conversion = metrics.get('fcf_conversion')
    free_cash_flow = metrics.get('free_cash_flow')
    net_income     = metrics.get('net_income')

    if free_cash_flow is not None and free_cash_flow < 0:
        flags.append(_flag(
            code     = 'negative_fcf',
            severity = 'warning',
            metric   = 'free_cash_flow',
            title    = 'Negative Free Cash Flow',
            message  = (
                "Free cash flow is negative, meaning the company is spending "
                "more cash than it generates from operations. This may reflect "
                "a deliberate high-growth investment phase, or it may signal "
                "financial stress. Check capital expenditure trends."
            ),
        ))

    elif (fcf_conversion is not None and fcf_conversion > 2.5
          and net_income is not None and net_income > 0):
        flags.append(_flag(
            code     = 'high_fcf_conversion',
            severity = 'info',
            metric   = 'fcf_conversion',
            title    = 'FCF Exceeds Earnings',
            message  = (
                f"Free cash flow is {fcf_conversion:.1f}× net income. "
                "This usually means large non-cash charges (e.g. acquisition-"
                "related amortization) are depressing reported earnings. "
                "Cash generation is actually stronger than the income statement suggests."
            ),
        ))

    elif (fcf_conversion is not None and 0 < fcf_conversion < 0.5
          and net_income is not None and net_income > 0):
        flags.append(_flag(
            code     = 'low_fcf_conversion',
            severity = 'warning',
            metric   = 'fcf_conversion',
            title    = 'Low FCF Conversion',
            message  = (
                f"Only {fcf_conversion:.0%} of net income converted to free "
                "cash flow. This may indicate aggressive revenue recognition, "
                "working capital buildup, or high capital reinvestment needs. "
                "Treat reported earnings with caution."
            ),
        ))

    # ── Debt & leverage ───────────────────────────────────────────────────────

    debt_ratio        = metrics.get('debt_ratio')
    interest_coverage = metrics.get('interest_coverage')

    if sector not in HIGH_LEVERAGE_SECTORS:
        if debt_ratio is not None and debt_ratio > 0.70:
            flags.append(_flag(
                code     = 'high_debt_ratio',
                severity = 'warning',
                metric   = 'debt_ratio',
                title    = 'High Debt Ratio',
                message  = (
                    f"Debt ratio of {debt_ratio:.0%} is elevated for a "
                    f"{sector or 'non-financial'} company. High leverage "
                    "amplifies losses during downturns and limits financial "
                    "flexibility. Monitor interest coverage closely."
                ),
            ))
    else:
        if debt_ratio is not None and debt_ratio > 0.70:
            flags.append(_flag(
                code     = 'sector_normal_leverage',
                severity = 'info',
                metric   = 'debt_ratio',
                title    = 'Sector-Normal Leverage',
                message  = (
                    f"A debt ratio of {debt_ratio:.0%} is structurally normal "
                    f"for {sector}. This metric is not directly comparable "
                    "to companies in other sectors."
                ),
            ))

    if interest_coverage is not None and 0 < interest_coverage < 3:
        flags.append(_flag(
            code     = 'low_interest_coverage',
            severity = 'warning',
            metric   = 'interest_coverage',
            title    = 'Low Interest Coverage',
            message  = (
                f"Interest coverage of {interest_coverage:.1f}× means operating "
                "profit covers interest payments only {interest_coverage:.1f} "
                "times. Below 3× is considered a risk threshold — a revenue "
                "decline could create debt servicing difficulties."
            ),
        ))

    # ── Liquidity ─────────────────────────────────────────────────────────────

    current_ratio = metrics.get('current_ratio')

    if current_ratio is not None and current_ratio < 1.0:
        flags.append(_flag(
            code     = 'low_current_ratio',
            severity = 'warning' if current_ratio < 0.8 else 'info',
            metric   = 'current_ratio',
            title    = 'Current Ratio Below 1',
            message  = (
                f"Current ratio of {current_ratio:.2f}x means current liabilities "
                "exceed current assets. "
                + (
                    "This is a potential short-term liquidity concern."
                    if current_ratio < 0.8
                    else
                    "Many large companies intentionally run lean balance sheets "
                    "when they have reliable access to credit markets."
                )
            ),
        ))

    # ── Data completeness ─────────────────────────────────────────────────────

    if metrics.get('revenue') is None or metrics.get('net_income') is None:
        flags.append(_flag(
            code     = 'incomplete_financials',
            severity = 'warning',
            metric   = 'revenue',
            title    = 'Incomplete Financial Data',
            message  = (
                "Some core financial statement data is missing. "
                "Ratios that depend on revenue or net income may show as N/A. "
                "This can occur for recently listed companies or data provider gaps."
            ),
        ))

    if metrics.get('interest_expense') is None and sector not in HIGH_LEVERAGE_SECTORS:
        # Only flag if they have meaningful debt but no interest expense data
        if debt_ratio is not None and debt_ratio > 0.20:
            flags.append(_flag(
                code     = 'missing_interest_expense',
                severity = 'info',
                metric   = 'interest_coverage',
                title    = 'Interest Coverage Unavailable',
                message  = (
                    "Interest expense data is not available from the data source. "
                    "Interest coverage ratio cannot be calculated despite the "
                    "company carrying meaningful debt."
                ),
            ))

    # Sort: warnings before info
    flags.sort(key=lambda f: 0 if f['severity'] == 'warning' else 1)
    return flags


# ── Test block ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    from analysis.metrics import calculate_all_metrics

    # ABBV is the ideal test case — triggers multiple flags:
    # negative equity, high FCF conversion, extreme PE, payout > 100%
    test_tickers = ['MMM', 'ABBV', 'ABT']

    print("=" * 65)
    print("edge_cases.py — test run")
    print("=" * 65)

    for ticker in test_tickers:
        metrics = calculate_all_metrics(ticker)
        if not metrics:
            print(f"\n{ticker}: no data — run bootstrap first")
            continue

        flags = check(metrics)
        company = metrics.get('company_name', ticker)

        print(f"\n{'─' * 50}")
        print(f"  {ticker}  —  {company}")
        print(f"  Sector: {metrics.get('sector', 'Unknown')}")
        print(f"{'─' * 50}")

        if not flags:
            print("  No edge cases detected ✅")
        else:
            for flag in flags:
                icon = '⚠️ ' if flag['severity'] == 'warning' else 'ℹ️ '
                print(f"\n  {icon} [{flag['code']}]  metric: {flag['metric']}")
                print(f"     Title  : {flag['title']}")
                # Wrap message at 60 chars for readability
                words   = flag['message'].split()
                line    = '     Message: '
                for word in words:
                    if len(line) + len(word) > 72:
                        print(line)
                        line = '               ' + word + ' '
                    else:
                        line += word + ' '
                if line.strip():
                    print(line)

    print(f"\n{'=' * 65}\n")