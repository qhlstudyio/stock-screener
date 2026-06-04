# analysis/valuation.py
# Computes valuation estimates and composite scores for each stock.
#
# Public interface (unchanged — screener.py requires no modification):
#   get_current_price(ticker)           → float | None
#   calculate_pe_valuation(ticker)      → dict | None
#   calculate_dcf(ticker)               → dict | None   (base scenario, backward compat)
#   calculate_dcf_scenarios(ticker)     → dict | None   (bear / base / bull)
#   calculate_graham_number(ticker)     → dict | None
#   calculate_composite_score(ticker)   → dict | None

import sys
import os
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db import get_financial_data, get_stock_prices
from analysis.metrics import calculate_all_metrics


# ── DCF assumptions ────────────────────────────────────────────────────────────

DCF_TERMINAL_RATE = 0.03    # long-term perpetual growth after projection window (3%)
DCF_DISCOUNT_RATE = 0.10    # required rate of return / WACC proxy (10%)
DCF_YEARS         = 5       # projection window in years

# Three growth scenarios applied during the projection window
DCF_SCENARIOS = {
    'bear': {'growth_rate': 0.05, 'label': 'Bear  (5%)'},
    'base': {'growth_rate': 0.08, 'label': 'Base  (8%)'},
    'bull': {'growth_rate': 0.12, 'label': 'Bull (12%)'},
}


# ── Scoring helper ─────────────────────────────────────────────────────────────

def _linear_score(value, worst, best, max_points):
    """
    Map a value linearly from [worst, best] → [0, max_points].
    Values outside the range are clamped to 0 or max_points.

    Works for both directions:
      Higher is better: worst < best  (e.g. gross margin 0% → 80%)
      Lower is better:  worst > best  (e.g. debt ratio 80% → 0%)
    """
    if value is None:
        return 0.0
    if best == worst:
        return 0.0
    ratio = (value - worst) / (best - worst)
    ratio = max(0.0, min(1.0, ratio))
    return round(ratio * max_points, 2)


# ── Part 1: Current price ──────────────────────────────────────────────────────

def get_current_price(ticker: str) -> float | None:
    """
    Return the most recent closing price from stock_prices.
    Returns None if no price data exists.
    """
    prices = get_stock_prices(ticker)
    if prices is None or prices.empty:
        return None
    return float(prices['close'].iloc[-1])


# ── Part 2: Relative valuation (P/E) ──────────────────────────────────────────

def calculate_pe_valuation(ticker: str) -> dict | None:
    """
    Compare the stock's trailing P/E against a flat market benchmark (25x).

    A flat benchmark is used intentionally — sector-adjusted benchmarks are
    deferred until enough per-sector data has accumulated (see CONTEXT.md).

    Returns
    -------
    pe_ratio     : trailing P/E stored in financial_data
    benchmark_pe : 25.0 (S&P 500 historical long-run average)
    pe_discount  : (benchmark - pe) / benchmark
                   positive → cheaper than benchmark
                   negative → more expensive
    pe_signal    : 'undervalued' | 'fairly valued' | 'overvalued'
                   thresholds: ±15% from benchmark
    """
    data = get_financial_data(ticker)
    if not data:
        return None

    pe_ratio = data.get('pe_ratio')
    if pe_ratio is None:
        return None

    BENCHMARK_PE = 25.0
    pe_discount  = (BENCHMARK_PE - pe_ratio) / BENCHMARK_PE

    if pe_discount > 0.15:
        signal = 'undervalued'
    elif pe_discount < -0.15:
        signal = 'overvalued'
    else:
        signal = 'fairly valued'

    return {
        'pe_ratio':     round(pe_ratio, 2),
        'benchmark_pe': BENCHMARK_PE,
        'pe_discount':  round(pe_discount, 4),
        'pe_signal':    signal,
    }


# ── Part 3: Graham Number ──────────────────────────────────────────────────────

def calculate_graham_number(ticker: str) -> dict | None:
    """
    Ben Graham's conservative intrinsic value floor.

    Formula: Graham Number = sqrt(22.5 × EPS × BVPS)
      22.5  = 15 (Graham's max P/E) × 1.5 (Graham's max P/B)
      EPS   = trailing earnings per share
      BVPS  = book value per share = shareholders_equity / shares_outstanding

    Limitations and when it returns None:
      - EPS ≤ 0: company is unprofitable; formula produces imaginary number
      - shareholders_equity ≤ 0: negative book value (e.g. post-acquisition
        goodwill exceeds equity); formula not meaningful
      - shares_outstanding missing: cannot compute BVPS

    The Graham Number is a conservative lower bound — most quality growth
    companies trade well above it. It is most useful as a sanity check and
    for value-oriented screening.

    Returns
    -------
    graham_number      : intrinsic value floor per share
    current_price      : latest closing price
    book_value_per_share : shareholders_equity / shares_outstanding
    margin_to_graham   : (graham - price) / graham
                         positive → below Graham floor (deep value territory)
                         negative → above Graham floor (typical for growth)
    graham_signal      : 'below graham' | 'near graham' | 'above graham'
    """
    data = get_financial_data(ticker)
    if not data:
        return None

    eps                 = data.get('eps')
    shareholders_equity = data.get('shareholders_equity')
    shares_outstanding  = data.get('shares_outstanding')

    # Validate pre-conditions
    if eps is None or eps <= 0:
        return None
    if shareholders_equity is None or shareholders_equity <= 0:
        return None
    if not shares_outstanding or shares_outstanding <= 0:
        return None

    current_price = get_current_price(ticker)
    if not current_price or current_price <= 0:
        return None

    bvps          = shareholders_equity / shares_outstanding
    graham_number = math.sqrt(22.5 * eps * bvps)
    margin        = (graham_number - current_price) / graham_number

    if margin > 0.15:
        signal = 'below graham'
    elif margin < -0.15:
        signal = 'above graham'
    else:
        signal = 'near graham'

    return {
        'graham_number':       round(graham_number, 2),
        'current_price':       round(current_price, 2),
        'book_value_per_share': round(bvps, 2),
        'margin_to_graham':    round(margin, 4),
        'graham_signal':       signal,
    }


# ── Part 4: DCF intrinsic value ────────────────────────────────────────────────

def _run_dcf_scenario(
    fcf:           float,
    shares:        float,
    current_price: float,
    growth_rate:   float,
    terminal_rate: float = DCF_TERMINAL_RATE,
    discount_rate: float = DCF_DISCOUNT_RATE,
    years:         int   = DCF_YEARS,
) -> dict:
    """
    Two-stage DCF for a single growth scenario.

    Stage 1: Project FCF for `years` at `growth_rate`, discount to PV.
    Stage 2: Gordon Growth Model terminal value, discounted to PV.
    Divide total PV by shares to get intrinsic value per share.

    Returns a dict with intrinsic_value, margin_of_safety, dcf_signal,
    and the growth_rate used.
    """
    pv_fcf        = 0.0
    projected_fcf = fcf

    for year in range(1, years + 1):
        projected_fcf *= (1 + growth_rate)
        pv_fcf        += projected_fcf / (1 + discount_rate) ** year

    terminal_fcf   = projected_fcf * (1 + terminal_rate)
    terminal_value = terminal_fcf / (discount_rate - terminal_rate)
    pv_terminal    = terminal_value / (1 + discount_rate) ** years

    intrinsic_value  = (pv_fcf + pv_terminal) / shares
    margin_of_safety = (intrinsic_value - current_price) / intrinsic_value

    if margin_of_safety > 0.15:
        signal = 'undervalued'
    elif margin_of_safety < -0.15:
        signal = 'overvalued'
    else:
        signal = 'fairly valued'

    return {
        'intrinsic_value':  round(intrinsic_value, 2),
        'current_price':    round(current_price, 2),
        'margin_of_safety': round(margin_of_safety, 4),
        'dcf_signal':       signal,
        'growth_rate':      growth_rate,
    }


def calculate_dcf_scenarios(ticker: str) -> dict | None:
    """
    Run bear / base / bull DCF scenarios and return all three results.

    Uses shares_outstanding from financial_data directly — more accurate than
    deriving shares from market_cap / price (which fluctuates intraday).

    Returns None if FCF ≤ 0 (DCF is not meaningful for cash-burning companies).

    Returns
    -------
    {
        'bear':          { intrinsic_value, margin_of_safety, dcf_signal, growth_rate, current_price }
        'base':          { ... }
        'bull':          { ... }
        'current_price': float
        'fcf':           float   (FCF used as starting point)
        'shares':        float
    }
    """
    data = get_financial_data(ticker)
    if not data:
        return None

    fcf    = data.get('free_cash_flow')
    shares = data.get('shares_outstanding')

    if not fcf or fcf <= 0:
        return None

    # shares_outstanding is more stable than market_cap / price
    if not shares or shares <= 0:
        # Fallback: derive from market_cap / current_price
        market_cap    = data.get('market_cap')
        current_price = get_current_price(ticker)
        if not market_cap or not current_price or current_price <= 0:
            return None
        shares = market_cap / current_price
    else:
        current_price = get_current_price(ticker)
        if not current_price or current_price <= 0:
            return None

    results = {}
    for scenario_key, scenario_cfg in DCF_SCENARIOS.items():
        results[scenario_key] = _run_dcf_scenario(
            fcf=fcf,
            shares=shares,
            current_price=current_price,
            growth_rate=scenario_cfg['growth_rate'],
        )

    results['current_price'] = round(current_price, 2)
    results['fcf']           = fcf
    results['shares']        = shares

    return results


def calculate_dcf(ticker: str) -> dict | None:
    """
    Base-case DCF estimate.
    Wrapper around calculate_dcf_scenarios() for backward compatibility
    with screener.py and valuation scoring — returns only the base scenario dict.

    Returns
    -------
    Same dict structure as before:
        intrinsic_value, current_price, margin_of_safety, dcf_signal
    """
    scenarios = calculate_dcf_scenarios(ticker)
    if scenarios is None:
        return None
    return scenarios['base']


# ── Part 5: Composite score (0-100, continuous linear) ────────────────────────
#
# Scoring ranges (flat benchmarks — industry adjustment deferred):
#
#   Component       worst    best    max_pts   direction
#   gross_margin    0%       80%     15        higher is better
#   profit_margin   0%       30%     15        higher is better
#   roe             0%       40%     20        higher is better
#   debt_ratio      80%      0%      15        lower is better
#   pe_discount    -30%     +30%     15        higher is better
#   dcf_mos        -50%     +50%     20        higher is better
#
# Note: ROE clamped at 0 when negative (e.g. negative equity companies like MCD)
# and clamped at max_points when very high (e.g. buyback-driven ROE like AAPL).
# These edge cases are flagged by edge_cases.py for user context.

def calculate_composite_score(ticker: str) -> dict | None:
    """
    Combine quality and valuation into a continuous 0-100 score.

    Uses _linear_score() throughout — no cliff effects. A 0.1% difference
    in a metric produces only a proportional point difference.

    Returns
    -------
    ticker    : stock ticker
    score     : total score (float, 0-100)
    breakdown : points earned per component (for UI score breakdown chart)
    """
    metrics = calculate_all_metrics(ticker)
    if not metrics:
        return None

    pe_val  = calculate_pe_valuation(ticker)
    dcf_val = calculate_dcf(ticker)

    breakdown = {}

    breakdown['gross_margin']  = _linear_score(
        metrics.get('gross_margin'),  worst=0.00, best=0.80, max_points=15)

    breakdown['profit_margin'] = _linear_score(
        metrics.get('profit_margin'), worst=0.00, best=0.30, max_points=15)

    breakdown['roe']           = _linear_score(
        metrics.get('roe'),           worst=0.00, best=0.40, max_points=20)

    breakdown['debt_ratio']    = _linear_score(
        metrics.get('debt_ratio'),    worst=0.80, best=0.00, max_points=15)

    pe_discount = pe_val.get('pe_discount') if pe_val else None
    breakdown['pe_valuation']  = _linear_score(
        pe_discount,                  worst=-0.30, best=0.30, max_points=15)

    mos = dcf_val.get('margin_of_safety') if dcf_val else None
    breakdown['dcf_valuation'] = _linear_score(
        mos,                          worst=-0.50, best=0.50, max_points=20)

    total_score = round(sum(breakdown.values()), 1)

    return {
        'ticker':    ticker,
        'score':     total_score,
        'breakdown': breakdown,
    }


# ── Test block ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':

    # Use tickers confirmed present after bootstrap --limit 5
    test_tickers = ['MMM', 'ABBV', 'ABT']

    print("=" * 65)
    print("valuation.py — test run")
    print("=" * 65)

    for ticker in test_tickers:
        print(f"\n{'─' * 50}")
        print(f"  {ticker}")
        print(f"{'─' * 50}")

        # P/E
        pe = calculate_pe_valuation(ticker)
        if pe:
            print(f"  [P/E]     {pe['pe_ratio']}x  "
                  f"(benchmark {pe['benchmark_pe']}x)  "
                  f"discount={pe['pe_discount']:.1%}  "
                  f"→ {pe['pe_signal']}")
        else:
            print(f"  [P/E]     no data")

        # Graham Number
        gn = calculate_graham_number(ticker)
        if gn:
            print(f"  [Graham]  ${gn['graham_number']}  "
                  f"(price ${gn['current_price']})  "
                  f"margin={gn['margin_to_graham']:.1%}  "
                  f"→ {gn['graham_signal']}")
        else:
            print(f"  [Graham]  not applicable "
                  f"(EPS ≤ 0 or negative equity or missing shares)")

        # DCF three scenarios
        scenarios = calculate_dcf_scenarios(ticker)
        if scenarios:
            for key in ('bear', 'base', 'bull'):
                s = scenarios[key]
                print(f"  [DCF {key}] intrinsic=${s['intrinsic_value']}  "
                      f"MoS={s['margin_of_safety']:.1%}  "
                      f"→ {s['dcf_signal']}")
        else:
            print(f"  [DCF]     not applicable (FCF ≤ 0 or missing data)")

        # Composite score
        score = calculate_composite_score(ticker)
        if score:
            print(f"  [Score]   {score['score']} / 100")
            for component, pts in score['breakdown'].items():
                bar = '█' * int(pts) + '░' * (
                    {'gross_margin':15,'profit_margin':15,'roe':20,
                     'debt_ratio':15,'pe_valuation':15,'dcf_valuation':20}[component] - int(pts)
                )
                print(f"            {component:<20} {pts:5.1f} pts  {bar}")
        else:
            print(f"  [Score]   no data")

    print(f"\n{'=' * 65}\n")