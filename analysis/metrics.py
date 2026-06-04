# analysis/metrics.py
# Computes financial metrics from stored fundamental data.
#
# Design principle:
#   Only raw data is stored in the database. All ratios and derived metrics
#   are calculated here at runtime. This module is the single source of truth
#   for every metric used in the system.
#
# yfinance format notes (confirmed against live data, yfinance 1.4.x):
#   dividend_yield      → already in PERCENTAGE form (0.81 means 0.81%)
#                         DO NOT multiply by 100. Display as-is with a % sign.
#   payout_ratio        → decimal form (0.35 means 35%). Standard.
#   capital_expenditures→ NEGATIVE (cash outflow convention from yfinance).
#                         Always use abs() when computing ratios.
#   interest_expense    → sign is inconsistent across yfinance versions.
#                         Always use abs() when computing interest coverage.
#   All financial statement values (revenue, net_income, etc.) → absolute USD.
#   All market multiples (pe_ratio, ev_ebitda, beta, etc.) → raw multiplier.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db import get_financial_data


# ── Helper ─────────────────────────────────────────────────────────────────────

def _safe_divide(numerator, denominator):
    """
    Return numerator / denominator.
    Returns None if either input is None, or if denominator is 0.
    Does NOT handle sign — caller is responsible for abs() where needed.
    """
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


# ── Main ───────────────────────────────────────────────────────────────────────

def calculate_all_metrics(ticker: str) -> dict | None:
    """
    Fetch financial data once and compute all metrics in a single pass.

    Raw fields are also passed through so downstream modules (valuation.py,
    screener.py, edge_cases.py) do not need to re-query the database.

    Returns a flat dict, or None if no data exists for the ticker.

    ── Metric Reference ─────────────────────────────────────────────────────────

    PROFITABILITY MARGINS
    ─────────────────────
    gross_margin = Gross Profit / Revenue
        Revenue remaining after direct production costs (COGS), before
        operating expenses. Reflects pricing power and competitive moat.
        Benchmark: > 40% strong; software companies often exceed 70%.

    operating_margin = Operating Income / Revenue
        Revenue remaining after both COGS and operating expenses (SG&A, R&D).
        The gap between gross_margin and operating_margin shows how much the
        company spends on running the business vs producing the product.
        Benchmark: > 15% healthy; > 25% strong.

    profit_margin = Net Income / Revenue
        Final bottom-line profitability after all costs, interest, and taxes.
        Benchmark: > 20% strong for most industries.

    fcf_margin = Free Cash Flow / Revenue
        Cash-based equivalent of profit margin. Harder to manipulate than
        accounting income — depreciation, working capital, and CapEx are all
        already reflected. Generally considered the most reliable margin.
        Benchmark: > 15% excellent.

    RETURN METRICS
    ──────────────
    roe = Net Income / Shareholders' Equity
        Profit generated per dollar of shareholders' capital.
        ⚠️  Two edge cases distort this metric (flagged by edge_cases.py):
          - Massive share buybacks shrink equity → ROE > 100% (AAPL). This is
            generally shareholder-friendly, not a red flag.
          - Negative equity → ROE is negative and meaningless (MCD).
        Benchmark: > 15% healthy; > 25% excellent.

    roa = Net Income / Total Assets
        Profit generated per dollar of total assets (debt + equity).
        Less sensitive than ROE to capital structure choices.
        Benchmark: > 5% acceptable; > 10% excellent.

    roic = Net Income / (Total Debt + Shareholders' Equity)
        Approximate return on all invested capital (debt + equity combined).
        Note: uses Net Income as a proxy for NOPAT (Net Operating Profit
        After Tax) — the proper ROIC formula would require a tax rate
        calculation not available from stored data.
        Benchmark: > 10% means value creation above cost of capital.

    LEVERAGE & LIQUIDITY
    ─────────────────────
    debt_ratio = Total Debt / Total Assets
        Share of assets financed by debt. High debt amplifies both returns
        and losses. Structurally high for banks and REITs (flagged by
        edge_cases.py).
        Benchmark: < 50% conservative; banks/REITs operate at 70-90% normally.

    d_e_ratio = Total Debt / Shareholders' Equity
        Debt per dollar of equity. Negative when equity is negative (e.g. MCD)
        — meaningless in that case. Flagged by edge_cases.py.
        Benchmark: < 1.0 conservative.

    interest_coverage = Operating Income / abs(Interest Expense)
        How many times the company can cover its interest payments from
        operating profit. abs() applied because yfinance sign is inconsistent.
        Benchmark: > 5 healthy; < 3 concerning; < 1.5 dangerous.

    current_ratio = Current Assets / Current Liabilities
        Short-term liquidity. Can the company pay its near-term bills?
        Benchmark: > 1.5 healthy; < 1.0 short-term stress.

    CASH FLOW QUALITY
    ─────────────────
    fcf_conversion = Free Cash Flow / Net Income
        How much of accounting profit converts to actual cash.
        > 1.0 means FCF exceeds reported earnings (strong quality signal).
        < 0.5 means earnings quality is questionable.

    EFFICIENCY
    ──────────
    capex_ratio = abs(Capital Expenditures) / Revenue
        How much of revenue is reinvested in capital assets.
        abs() required — yfinance returns capex as a negative number.
        Heavy industries (manufacturing, telco): 10-20%.
        Asset-light (software, services): < 5%.

    rd_ratio = Research & Development / Revenue
        Innovation investment intensity. High R&D sustained over years is a
        moat indicator; one-time spikes are less meaningful.
        Note: not all companies report R&D (e.g. retailers). None = N/A.

    revenue_per_employee = Revenue / Full-Time Employees
        Revenue generated per person — a rough productivity benchmark.
        Useful for same-sector comparisons. In USD.
        Software firms: $500K–$2M+. Retailers: $100K–$300K.

    ─────────────────────────────────────────────────────────────────────────────
    """
    data = get_financial_data(ticker)
    if not data:
        return None

    # ── Extract raw fields ─────────────────────────────────────────────────────
    revenue              = data.get('revenue')
    net_income           = data.get('net_income')
    gross_profit         = data.get('gross_profit')
    operating_income     = data.get('operating_income')
    total_assets         = data.get('total_assets')
    total_debt           = data.get('total_debt')
    shareholders_equity  = data.get('shareholders_equity')
    current_assets       = data.get('current_assets')
    current_liabilities  = data.get('current_liabilities')
    free_cash_flow       = data.get('free_cash_flow')
    capital_expenditures = data.get('capital_expenditures')   # negative in yfinance
    interest_expense     = data.get('interest_expense')       # sign inconsistent
    research_development = data.get('research_development')
    full_time_employees  = data.get('full_time_employees')

    # ── Computed metrics ───────────────────────────────────────────────────────

    # Profitability margins (all in decimal form: 0.25 = 25%)
    gross_margin     = _safe_divide(gross_profit,    revenue)
    operating_margin = _safe_divide(operating_income, revenue)
    profit_margin    = _safe_divide(net_income,       revenue)
    fcf_margin       = _safe_divide(free_cash_flow,   revenue)

    # Return metrics
    roe  = _safe_divide(net_income, shareholders_equity)
    roa  = _safe_divide(net_income, total_assets)
    roic = _safe_divide(
        net_income,
        (total_debt + shareholders_equity)
        if (total_debt is not None and shareholders_equity is not None) else None
    )

    # Leverage & liquidity
    debt_ratio = _safe_divide(total_debt, total_assets)
    d_e_ratio  = _safe_divide(total_debt, shareholders_equity)

    # Interest coverage: abs() on both sides for safety
    # Operating income can also be negative; result will be negative in that case
    # (edge_cases.py will flag interest_coverage < 3)
    interest_coverage = _safe_divide(
        operating_income,
        abs(interest_expense) if interest_expense is not None else None
    )

    current_ratio = _safe_divide(current_assets, current_liabilities)

    # Cash flow quality
    fcf_conversion = _safe_divide(free_cash_flow, net_income)

    # Efficiency
    # capex is negative in yfinance → abs() to get the actual spend amount
    capex_ratio = _safe_divide(
        abs(capital_expenditures) if capital_expenditures is not None else None,
        revenue
    )
    rd_ratio            = _safe_divide(research_development, revenue)
    revenue_per_employee = _safe_divide(revenue, full_time_employees)

    return {
        # ── Identity ───────────────────────────────────────────────────────────
        'ticker':       ticker,
        'company_name': data.get('company_name'),
        'exchange':     data.get('exchange'),
        'sector':       data.get('sector'),
        'industry':     data.get('industry'),

        # ── Computed: profitability margins (decimal, e.g. 0.25 = 25%) ────────
        'gross_margin':     gross_margin,
        'operating_margin': operating_margin,
        'profit_margin':    profit_margin,
        'fcf_margin':       fcf_margin,

        # ── Computed: returns (decimal) ────────────────────────────────────────
        'roe':  roe,
        'roa':  roa,
        'roic': roic,

        # ── Computed: leverage & liquidity ─────────────────────────────────────
        'debt_ratio':         debt_ratio,
        'd_e_ratio':          d_e_ratio,
        'interest_coverage':  interest_coverage,   # multiplier, e.g. 5.0 = 5×
        'current_ratio':      current_ratio,       # multiplier, e.g. 1.5

        # ── Computed: cash flow quality ────────────────────────────────────────
        'fcf_conversion': fcf_conversion,          # multiplier, e.g. 1.1

        # ── Computed: efficiency ───────────────────────────────────────────────
        'capex_ratio':          capex_ratio,           # decimal
        'rd_ratio':             rd_ratio,              # decimal, None if not reported
        'revenue_per_employee': revenue_per_employee,  # USD per person

        # ── Raw pass-through: market pricing ───────────────────────────────────
        # These come directly from yfinance stock.info — no transformation applied.
        'market_cap':       data.get('market_cap'),
        'enterprise_value': data.get('enterprise_value'),
        'ev_ebitda':        data.get('ev_ebitda'),
        'ev_revenue':       data.get('ev_revenue'),
        'pe_ratio':         data.get('pe_ratio'),
        'forward_pe':       data.get('forward_pe'),
        'eps':              data.get('eps'),
        'forward_eps':      data.get('forward_eps'),
        'shares_outstanding': data.get('shares_outstanding'),

        # ── Raw pass-through: financial statement values (absolute USD) ─────────
        'revenue':              revenue,
        'net_income':           net_income,
        'gross_profit':         gross_profit,
        'operating_income':     operating_income,
        'free_cash_flow':       free_cash_flow,
        'capital_expenditures': capital_expenditures,  # kept negative (raw value)
        'interest_expense':     interest_expense,
        'research_development': research_development,
        'total_assets':         total_assets,
        'total_debt':           total_debt,
        'shareholders_equity':  shareholders_equity,
        'current_assets':       current_assets,
        'current_liabilities':  current_liabilities,

        # ── Raw pass-through: dividends ────────────────────────────────────────
        # dividend_yield is in PERCENTAGE form from yfinance (0.81 = 0.81%).
        # Display directly — do not divide by 100.
        # payout_ratio is in DECIMAL form (0.35 = 35%). Standard convention.
        'dividend_yield': data.get('dividend_yield'),
        'dividend_rate':  data.get('dividend_rate'),
        'payout_ratio':   data.get('payout_ratio'),

        # ── Raw pass-through: risk ─────────────────────────────────────────────
        'beta': data.get('beta'),     # raw multiplier, e.g. 1.093

        # ── Raw pass-through: analyst consensus ────────────────────────────────
        'target_mean_price':  data.get('target_mean_price'),
        'target_high_price':  data.get('target_high_price'),
        'target_low_price':   data.get('target_low_price'),
        'analyst_count':      data.get('analyst_count'),
        'recommendation_key': data.get('recommendation_key'),
    }


# ── Test block ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    # Use tickers likely to be in the DB after bootstrap --limit 5
    test_tickers = ['MMM', 'MSFT', 'ABBV']

    print("=" * 65)
    print("metrics.py — test run")
    print("=" * 65)

    all_passed = True

    for ticker in test_tickers:
        metrics = calculate_all_metrics(ticker)
        if not metrics:
            print(f"\n{ticker}: no data in database — run bootstrap first")
            all_passed = False
            continue

        print(f"\n{'─' * 45}")
        print(f"  {ticker}  —  {metrics.get('company_name', '?')}")
        print(f"  {metrics.get('sector', '?')} / {metrics.get('industry', '?')}")
        print(f"{'─' * 45}")

        def _pct(v):
            return f"{v:.2%}" if v is not None else "None"

        def _x(v):
            return f"{v:.2f}x" if v is not None else "None"

        def _usd(v):
            if v is None:
                return "None"
            if abs(v) >= 1e9:
                return f"${v/1e9:.1f}B"
            if abs(v) >= 1e6:
                return f"${v/1e6:.1f}M"
            return f"${v:,.0f}"

        rows = [
            ("Profitability", None),
            ("  Gross Margin",      _pct(metrics['gross_margin'])),
            ("  Operating Margin",  _pct(metrics['operating_margin'])),
            ("  Profit Margin",     _pct(metrics['profit_margin'])),
            ("  FCF Margin",        _pct(metrics['fcf_margin'])),
            ("Returns", None),
            ("  ROE",               _pct(metrics['roe'])),
            ("  ROA",               _pct(metrics['roa'])),
            ("  ROIC",              _pct(metrics['roic'])),
            ("Leverage & Liquidity", None),
            ("  Debt Ratio",        _pct(metrics['debt_ratio'])),
            ("  D/E Ratio",         _x(metrics['d_e_ratio'])),
            ("  Interest Coverage", _x(metrics['interest_coverage'])),
            ("  Current Ratio",     _x(metrics['current_ratio'])),
            ("Cash Flow", None),
            ("  FCF Conversion",    _x(metrics['fcf_conversion'])),
            ("Efficiency", None),
            ("  CapEx Ratio",       _pct(metrics['capex_ratio'])),
            ("  R&D Ratio",         _pct(metrics['rd_ratio'])),
            ("  Revenue/Employee",  _usd(metrics['revenue_per_employee'])),
            ("Market Data", None),
            ("  P/E Trailing",      _x(metrics['pe_ratio'])),
            ("  P/E Forward",       _x(metrics['forward_pe'])),
            ("  EV/EBITDA",         _x(metrics['ev_ebitda'])),
            ("  Market Cap",        _usd(metrics['market_cap'])),
            ("Dividends", None),
            # dividend_yield is already %, so display it directly
            ("  Dividend Yield",
             f"{metrics['dividend_yield']}%" if metrics['dividend_yield'] is not None else "None"),
            ("  Payout Ratio",      _pct(metrics['payout_ratio'])),
            ("  Beta",              _x(metrics['beta'])),
        ]

        for label, value in rows:
            if value is None:
                print(f"\n  [{label}]")
            else:
                print(f"  {label:<25} {value}")

    print(f"\n{'=' * 65}")
    print(f"  Result: {'ALL DATA LOADED ✅' if all_passed else 'SOME TICKERS MISSING ❌'}")
    print(f"{'=' * 65}\n")