# analysis/screener.py
# Aggregates all analysis layers into a single stock profile.
# Supports batch filtering and sorting for the API layer.
#
# Main entry points:
#   build_stock_profile(ticker)          → dict | None   (single stock, full data)
#   screen_stocks(tickers, filters, ...) → list[dict]    (batch, filtered + sorted)
#   get_sectors_from_db()                → list[str]     (available sectors)

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from analysis.metrics      import calculate_all_metrics
from analysis.valuation    import (
    _linear_score,
    calculate_pe_valuation,
    calculate_dcf_scenarios,
    calculate_graham_number,
)
from analysis.risk_metrics import calculate_all_risk_metrics
from analysis import edge_cases


# ── Part 1: Single stock profile ───────────────────────────────────────────────

def build_stock_profile(ticker: str) -> dict | None:
    """
    Build a complete profile for one ticker by combining all analysis layers:
      - Metrics         (metrics.py)        — margins, returns, ratios
      - Valuation       (valuation.py)      — P/E, DCF scenarios, Graham Number
      - Composite score (valuation.py)      — 0-100 screening score
      - Risk metrics    (risk_metrics.py)   — beta, sharpe, drawdown, returns
      - Edge case flags (edge_cases.py)     — contextual warnings

    Returns a dict ready for JSON serialisation by the FastAPI layer.
    Returns None if no financial data exists for the ticker.

    Performance note:
      This function makes 3-4 database round trips (financial data, price data).
      It is designed for single-stock detail pages. For batch screening of many
      stocks, the price-data calls (risk metrics, current price) dominate.
      See screen_stocks() for batch usage.
    """
    # ── Financial metrics (one DB query) ───────────────────────────────────────
    metrics = calculate_all_metrics(ticker)
    if not metrics:
        return None

    # ── Valuation (reuses financial data cached in metrics) ────────────────────
    pe_val    = calculate_pe_valuation(ticker)
    dcf_scen  = calculate_dcf_scenarios(ticker)   # bear / base / bull
    dcf_base  = dcf_scen['base'] if dcf_scen else None   # backward compat
    graham    = calculate_graham_number(ticker)

    # ── Composite score (computed inline — avoids redundant DB queries) ────────
    # calculate_composite_score() would re-query financial data and price data
    # from scratch. We already have everything we need, so compute directly.
    pe_discount = pe_val.get('pe_discount') if pe_val else None
    mos         = dcf_base.get('margin_of_safety') if dcf_base else None

    score_breakdown = {
        'gross_margin':  _linear_score(metrics.get('gross_margin'),  0.00, 0.80, 15),
        'profit_margin': _linear_score(metrics.get('profit_margin'), 0.00, 0.30, 15),
        'roe':           _linear_score(metrics.get('roe'),           0.00, 0.40, 20),
        'debt_ratio':    _linear_score(metrics.get('debt_ratio'),    0.80, 0.00, 15),
        'pe_valuation':  _linear_score(pe_discount,                 -0.30, 0.30, 15),
        'dcf_valuation': _linear_score(mos,                         -0.50, 0.50, 20),
    }
    score = round(sum(score_breakdown.values()), 1)

    # ── Risk metrics (price history query) ────────────────────────────────────
    risk = calculate_all_risk_metrics(ticker)

    # ── Edge case flags (pure computation, no DB) ──────────────────────────────
    flags = edge_cases.check(metrics)

    # ── Assemble profile ───────────────────────────────────────────────────────
    return {

        # ── Identity ───────────────────────────────────────────────────────────
        'ticker':       ticker,
        'company_name': metrics.get('company_name'),
        'exchange':     metrics.get('exchange'),
        'sector':       metrics.get('sector'),
        'industry':     metrics.get('industry'),

        # ── Profitability margins (decimal: 0.25 = 25%) ────────────────────────
        'gross_margin':     metrics.get('gross_margin'),
        'operating_margin': metrics.get('operating_margin'),
        'profit_margin':    metrics.get('profit_margin'),
        'fcf_margin':       metrics.get('fcf_margin'),

        # ── Return metrics (decimal) ────────────────────────────────────────────
        'roe':  metrics.get('roe'),
        'roa':  metrics.get('roa'),
        'roic': metrics.get('roic'),

        # ── Leverage & liquidity ────────────────────────────────────────────────
        'debt_ratio':        metrics.get('debt_ratio'),
        'd_e_ratio':         metrics.get('d_e_ratio'),
        'interest_coverage': metrics.get('interest_coverage'),
        'current_ratio':     metrics.get('current_ratio'),

        # ── Cash flow ───────────────────────────────────────────────────────────
        'fcf_conversion': metrics.get('fcf_conversion'),

        # ── Efficiency ──────────────────────────────────────────────────────────
        'capex_ratio':           metrics.get('capex_ratio'),
        'rd_ratio':              metrics.get('rd_ratio'),
        'revenue_per_employee':  metrics.get('revenue_per_employee'),

        # ── Market pricing (raw from yfinance) ─────────────────────────────────
        'market_cap':         metrics.get('market_cap'),
        'enterprise_value':   metrics.get('enterprise_value'),
        'ev_ebitda':          metrics.get('ev_ebitda'),
        'ev_revenue':         metrics.get('ev_revenue'),
        'pe_ratio':           metrics.get('pe_ratio'),
        'forward_pe':         metrics.get('forward_pe'),
        'eps':                metrics.get('eps'),
        'forward_eps':        metrics.get('forward_eps'),
        'shares_outstanding': metrics.get('shares_outstanding'),

        # ── Financial statement values (absolute USD) ───────────────────────────
        'revenue':              metrics.get('revenue'),
        'net_income':           metrics.get('net_income'),
        'gross_profit':         metrics.get('gross_profit'),
        'operating_income':     metrics.get('operating_income'),
        'free_cash_flow':       metrics.get('free_cash_flow'),
        'total_assets':         metrics.get('total_assets'),
        'total_debt':           metrics.get('total_debt'),
        'shareholders_equity':  metrics.get('shareholders_equity'),
        'current_assets':       metrics.get('current_assets'),
        'current_liabilities':  metrics.get('current_liabilities'),
        'research_development': metrics.get('research_development'),
        'capital_expenditures': metrics.get('capital_expenditures'),

        # ── Dividends ────────────────────────────────────────────────────────────
        # dividend_yield: already in % form from yfinance (0.81 = 0.81%)
        'dividend_yield': metrics.get('dividend_yield'),
        'dividend_rate':  metrics.get('dividend_rate'),
        'payout_ratio':   metrics.get('payout_ratio'),

        # ── Risk (from yfinance) ─────────────────────────────────────────────────
        'beta_yf': metrics.get('beta'),   # yfinance pre-calculated beta

        # ── Analyst consensus ────────────────────────────────────────────────────
        'target_mean_price':  metrics.get('target_mean_price'),
        'target_high_price':  metrics.get('target_high_price'),
        'target_low_price':   metrics.get('target_low_price'),
        'analyst_count':      metrics.get('analyst_count'),
        'recommendation_key': metrics.get('recommendation_key'),

        # ── P/E valuation ─────────────────────────────────────────────────────
        'pe_discount': pe_val.get('pe_discount') if pe_val else None,
        'pe_signal':   pe_val.get('pe_signal')   if pe_val else None,

        # ── DCF valuation — base case (backward compatible) ───────────────────
        'intrinsic_value':  dcf_base.get('intrinsic_value')  if dcf_base else None,
        'current_price':    dcf_base.get('current_price')    if dcf_base else None,
        'margin_of_safety': dcf_base.get('margin_of_safety') if dcf_base else None,
        'dcf_signal':       dcf_base.get('dcf_signal')       if dcf_base else None,

        # ── DCF three scenarios ────────────────────────────────────────────────
        # Each sub-dict: {intrinsic_value, current_price, margin_of_safety,
        #                 dcf_signal, growth_rate}
        'dcf_scenarios': {
            'bear': dcf_scen.get('bear') if dcf_scen else None,
            'base': dcf_scen.get('base') if dcf_scen else None,
            'bull': dcf_scen.get('bull') if dcf_scen else None,
        } if dcf_scen else None,

        # ── Graham Number ──────────────────────────────────────────────────────
        'graham_number':       graham.get('graham_number')       if graham else None,
        'margin_to_graham':    graham.get('margin_to_graham')    if graham else None,
        'graham_signal':       graham.get('graham_signal')       if graham else None,
        'book_value_per_share': graham.get('book_value_per_share') if graham else None,

        # ── Composite score ────────────────────────────────────────────────────
        'score':           score,
        'score_breakdown': score_breakdown,

        # ── Statistical risk metrics (from price history) ──────────────────────
        'beta':          risk.get('beta')          if risk else None,
        'r_squared':     risk.get('r_squared')     if risk else None,
        'volatility':    risk.get('volatility')    if risk else None,
        'sharpe':        risk.get('sharpe')        if risk else None,
        'alpha':         risk.get('alpha')         if risk else None,
        'max_drawdown':  risk.get('max_drawdown')  if risk else None,

        # ── Price returns ──────────────────────────────────────────────────────
        'return_1m': risk.get('return_1m') if risk else None,
        'return_3m': risk.get('return_3m') if risk else None,
        'return_6m': risk.get('return_6m') if risk else None,
        'return_1y': risk.get('return_1y') if risk else None,

        # ── Relative performance vs SPY ────────────────────────────────────────
        'vs_spy_1m': risk.get('vs_spy_1m') if risk else None,
        'vs_spy_3m': risk.get('vs_spy_3m') if risk else None,
        'vs_spy_6m': risk.get('vs_spy_6m') if risk else None,
        'vs_spy_1y': risk.get('vs_spy_1y') if risk else None,

        # ── Edge case flags ────────────────────────────────────────────────────
        # List of dicts: {code, severity, metric, title, message}
        # Empty list means no anomalies detected.
        'edge_case_flags': flags,
    }


# ── Part 2: Batch screener ─────────────────────────────────────────────────────

def screen_stocks(
    tickers:   list[str] | None = None,
    filters:   dict | None      = None,
    sort_by:   str              = 'score',
    ascending: bool             = False,
) -> list[dict]:
    """
    Build profiles for all tickers, apply optional filters, then sort.

    Parameters
    ----------
    tickers   : ticker list. Falls back to config.ALL_TICKERS when None.
                In production, the FastAPI layer passes sector-filtered lists
                from the sp500_membership table.

    filters   : dict of filter conditions (all optional):
        min_score         (float) minimum composite score
        max_pe            (float) maximum trailing P/E
        min_roe           (float) minimum ROE, decimal (0.15 = 15%)
        max_debt_ratio    (float) maximum debt ratio, decimal (0.50 = 50%)
        min_profit_margin (float) minimum net profit margin
        min_gross_margin  (float) minimum gross margin
        sector            (str)   exact sector name match
        max_beta          (float) maximum calculated beta

    sort_by   : profile field to sort by (default: 'score')
    ascending : sort direction (default: False = highest first)

    Returns
    -------
    list[dict]  filtered and sorted profiles (never None)
    """
    if tickers is None:
        tickers = config.ALL_TICKERS

    if filters is None:
        filters = {}

    # Build profiles
    profiles = []
    failed   = []

    for ticker in tickers:
        profile = build_stock_profile(ticker)
        if profile:
            profiles.append(profile)
        else:
            failed.append(ticker)

    if failed:
        print(f"[screener] No data for: {', '.join(failed)}")

    # Apply filters
    def passes(p: dict) -> bool:
        if filters.get('min_score') is not None:
            if (p.get('score') or 0) < filters['min_score']:
                return False
        if filters.get('max_pe') is not None:
            pe = p.get('pe_ratio')
            if pe is None or pe > filters['max_pe']:
                return False
        if filters.get('min_roe') is not None:
            if (p.get('roe') or 0) < filters['min_roe']:
                return False
        if filters.get('max_debt_ratio') is not None:
            if (p.get('debt_ratio') or 1) > filters['max_debt_ratio']:
                return False
        if filters.get('min_profit_margin') is not None:
            if (p.get('profit_margin') or 0) < filters['min_profit_margin']:
                return False
        if filters.get('min_gross_margin') is not None:
            if (p.get('gross_margin') or 0) < filters['min_gross_margin']:
                return False
        if filters.get('sector') is not None:
            if p.get('sector') != filters['sector']:
                return False
        if filters.get('max_beta') is not None:
            beta = p.get('beta')
            if beta is not None and beta > filters['max_beta']:
                return False
        return True

    filtered = [p for p in profiles if passes(p)]

    # Sort — None values always sink to the bottom
    filtered.sort(
        key=lambda x: (
            x.get(sort_by) is not None,
            x.get(sort_by) or 0,
        ),
        reverse=not ascending,
    )

    return filtered


# ── Part 3: Utility ────────────────────────────────────────────────────────────

def get_sectors_from_db() -> list[str]:
    """
    Return the list of distinct sectors currently in financial_data.
    Used by the FastAPI /api/sectors endpoint and frontend sector selector.
    """
    from data.db import get_connection
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DISTINCT sector FROM financial_data
            WHERE sector IS NOT NULL
            ORDER BY sector ASC
        """)
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"[screener] get_sectors_from_db error: {e}")
        return []
    finally:
        conn.close()


def get_preset_groups() -> dict:
    """
    Return sector groups from config for backward compatibility.
    In v2, the frontend uses get_sectors_from_db() via the API instead.
    """
    return config.STOCKS


# ── Test block ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':

    print("=" * 65)
    print("screener.py — test run")
    print("=" * 65)

    # ── Test 1: Single full profile ────────────────────────────────────────────
    print("\n[Test 1] build_stock_profile('MMM') — full profile")
    profile = build_stock_profile('MMM')

    if profile and profile.get('score') is not None:
        print(f"  company      : {profile['company_name']}")
        print(f"  sector       : {profile['sector']}")
        print(f"  score        : {profile['score']} / 100")
        print(f"  gross_margin : {profile['gross_margin']:.2%}")
        print(f"  roe          : {profile['roe']:.2%}")
        print(f"  pe_signal    : {profile['pe_signal']}")
        print(f"  dcf_signal   : {profile['dcf_signal']}")
        print(f"  graham       : ${profile['graham_number']}  ({profile['graham_signal']})")
        print(f"  beta         : {profile['beta']}")
        print(f"  sharpe       : {profile['sharpe']}")
        print(f"  max_drawdown : {profile['max_drawdown']:.2%}")
        print(f"  1Y return    : {profile['return_1y']:.2%}")
        print(f"  1Y vs SPY    : {profile['vs_spy_1y']:.2%}")

        # DCF scenarios
        if profile.get('dcf_scenarios'):
            for key in ('bear', 'base', 'bull'):
                s = profile['dcf_scenarios'][key]
                if s:
                    print(f"  DCF {key}    : ${s['intrinsic_value']}  "
                          f"MoS={s['margin_of_safety']:.1%}  ({s['dcf_signal']})")

        # Edge case flags
        flags = profile.get('edge_case_flags', [])
        print(f"  flags        : {len(flags)} edge case(s)")
        for f in flags:
            icon = '⚠️' if f['severity'] == 'warning' else 'ℹ️'
            print(f"    {icon} [{f['code']}]  {f['title']}")

        print("  PASS ✅")
    else:
        print("  FAIL ❌ — profile None or missing score")

    # ── Test 2: ABBV (many flags expected) ────────────────────────────────────
    print("\n[Test 2] build_stock_profile('ABBV') — edge case heavy")
    profile = build_stock_profile('ABBV')
    if profile:
        flags = profile.get('edge_case_flags', [])
        print(f"  score        : {profile['score']} / 100")
        print(f"  pe_ratio     : {profile['pe_ratio']:.1f}x (trailing)")
        print(f"  forward_pe   : {profile['forward_pe']:.1f}x")
        print(f"  graham       : {'N/A (neg equity)' if not profile['graham_number'] else profile['graham_number']}")
        print(f"  beta         : {profile['beta']}")
        print(f"  r_squared    : {profile['r_squared']:.2%}")
        print(f"  flags ({len(flags)}):")
        for f in flags:
            icon = '⚠️' if f['severity'] == 'warning' else 'ℹ️'
            print(f"    {icon} {f['title']}")
        print("  PASS ✅" if len(flags) >= 3 else "  FAIL ❌ — expected ≥3 flags")
    else:
        print("  FAIL ❌")

    # ── Test 3: Batch screen with filters ─────────────────────────────────────
    print("\n[Test 3] screen_stocks(tickers, filters) — available DB tickers")
    available = ['MMM', 'AOS', 'ABT', 'ABBV', 'ACN']
    results   = screen_stocks(
        tickers=available,
        filters={'min_gross_margin': 0.30},
        sort_by='score',
    )
    print(f"  {len(results)} of {len(available)} passed gross_margin ≥ 30%:")
    for r in results:
        gm = f"{r['gross_margin']:.1%}" if r['gross_margin'] else '—'
        print(f"  {r['ticker']:<8} score={r['score']:<6} gross_margin={gm}")
    print("  PASS ✅" if isinstance(results, list) else "  FAIL ❌")

    # ── Test 4: get_sectors_from_db ───────────────────────────────────────────
    print("\n[Test 4] get_sectors_from_db()")
    sectors = get_sectors_from_db()
    if sectors:
        print(f"  {len(sectors)} sectors in DB: {sectors}")
        print("  PASS ✅")
    else:
        print("  FAIL ❌ — no sectors found (bootstrap may still be running)")

    print(f"\n{'=' * 65}\n")