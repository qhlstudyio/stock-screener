# analysis/valuation.py
# Computes valuation estimates and composite scores for each stock.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db import get_financial_data, get_stock_prices
from analysis.metrics import calculate_all_metrics


# ---------------------------------------------------------------------------
# DCF assumptions
# ---------------------------------------------------------------------------
DCF_GROWTH_RATE   = 0.08   # assumed annual FCF growth for next 5 years (8%)
DCF_TERMINAL_RATE = 0.03   # assumed long-term growth after year 5 (3%)
DCF_DISCOUNT_RATE = 0.10   # required rate of return / discount rate (10%)
DCF_YEARS         = 5      # projection window


# ---------------------------------------------------------------------------
# Scoring helper
# ---------------------------------------------------------------------------

def _linear_score(value, worst, best, max_points):
    """
    Map a value linearly from [worst, best] to [0, max_points].
    Values outside the range are clamped to 0 or max_points.

    Works for both directions:
      - Higher is better: worst < best  (e.g. gross margin)
      - Lower is better:  worst > best  (e.g. debt ratio)
    """
    if value is None:
        return 0.0
    if best == worst:
        return 0.0
    ratio = (value - worst) / (best - worst)
    ratio = max(0.0, min(1.0, ratio))   # clamp to [0, 1]
    return round(ratio * max_points, 2)


# ---------------------------------------------------------------------------
# Part 1: Current price
# ---------------------------------------------------------------------------

def get_current_price(ticker):
    """
    Retrieve the most recent closing price from the stock_prices table.
    Returns float or None.
    """
    prices = get_stock_prices(ticker)
    if prices is None or prices.empty:
        return None
    return float(prices['close'].iloc[-1])


# ---------------------------------------------------------------------------
# Part 2: Relative valuation (P/E)
# ---------------------------------------------------------------------------

def calculate_pe_valuation(ticker):
    """
    Compare the stock's P/E against a flat market benchmark.

    Returns dict:
        pe_ratio        : current P/E
        benchmark_pe    : comparison baseline (25x)
        pe_discount     : (benchmark - pe) / benchmark
                          positive = cheaper than benchmark
                          negative = more expensive
        pe_signal       : 'undervalued' | 'fairly valued' | 'overvalued'
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


# ---------------------------------------------------------------------------
# Part 3: DCF intrinsic value
# ---------------------------------------------------------------------------

def calculate_dcf(ticker):
    """
    Two-stage DCF estimate.

    Stage 1 : project FCF for DCF_YEARS at DCF_GROWTH_RATE, discount to PV.
    Stage 2 : terminal value via Gordon Growth Model, discounted to PV.
    Divide total PV by shares outstanding to get intrinsic value per share.

    Returns dict:
        intrinsic_value  : estimated fair value per share
        current_price    : latest closing price
        margin_of_safety : (intrinsic - price) / intrinsic
                           positive = stock below fair value
        dcf_signal       : 'undervalued' | 'fairly valued' | 'overvalued'
    """
    data = get_financial_data(ticker)
    if not data:
        return None

    fcf        = data.get('free_cash_flow')
    market_cap = data.get('market_cap')

    if not fcf or not market_cap or fcf <= 0:
        return None

    current_price = get_current_price(ticker)
    if not current_price or current_price <= 0:
        return None

    shares = market_cap / current_price

    # Stage 1
    pv_fcf        = 0
    projected_fcf = fcf
    for year in range(1, DCF_YEARS + 1):
        projected_fcf *= (1 + DCF_GROWTH_RATE)
        pv_fcf        += projected_fcf / (1 + DCF_DISCOUNT_RATE) ** year

    # Stage 2
    terminal_fcf   = projected_fcf * (1 + DCF_TERMINAL_RATE)
    terminal_value = terminal_fcf / (DCF_DISCOUNT_RATE - DCF_TERMINAL_RATE)
    pv_terminal    = terminal_value / (1 + DCF_DISCOUNT_RATE) ** DCF_YEARS

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
    }


# ---------------------------------------------------------------------------
# Part 4: Composite score  (0 – 100, continuous linear)
# ---------------------------------------------------------------------------
#
# Scoring ranges — intentionally documented here so future industry-adjustment
# upgrade can replace these flat ranges with sector-specific ones.
#
#   Metric          worst   best    max_pts  direction
#   gross_margin    0%      80%     15       higher is better
#   profit_margin   0%      30%     15       higher is better
#   roe             0%      40%     20       higher is better
#   debt_ratio      80%     0%      15       lower is better
#   pe_discount    -30%    +30%     15       higher is better
#   margin_of_safety -50%  +50%    20       higher is better
#
# TODO (future upgrade): replace flat ranges above with per-sector benchmarks.
# ---------------------------------------------------------------------------

def calculate_composite_score(ticker):
    """
    Combine quality and valuation into a continuous 0-100 score.

    All components use _linear_score(), which eliminates cliff effects:
    a 0.1% difference in a metric produces only a proportional point difference,
    never a sudden jump.

    Returns dict:
        ticker    : stock ticker
        score     : total score (float, 0-100)
        breakdown : points earned per component (for UI display)
    """
    metrics = calculate_all_metrics(ticker)
    if not metrics:
        return None

    pe_val  = calculate_pe_valuation(ticker)
    dcf_val = calculate_dcf(ticker)

    breakdown = {}

    # Quality components
    breakdown['gross_margin']  = _linear_score(
        metrics.get('gross_margin'),  worst=0.00, best=0.80, max_points=15)

    breakdown['profit_margin'] = _linear_score(
        metrics.get('profit_margin'), worst=0.00, best=0.30, max_points=15)

    breakdown['roe']           = _linear_score(
        metrics.get('roe'),           worst=0.00, best=0.40, max_points=20)

    # Debt ratio: lower is better → worst=0.80, best=0.00
    breakdown['debt_ratio']    = _linear_score(
        metrics.get('debt_ratio'),    worst=0.80, best=0.00, max_points=15)

    # Valuation components
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


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------

if __name__ == '__main__':

    test_tickers = ['AAPL', 'MSFT', 'GOOGL']
    all_passed   = True

    print("=" * 60)
    print("valuation.py — test run")
    print("=" * 60)

    for ticker in test_tickers:
        print(f"\n{'─' * 40}")
        print(f"  {ticker}")
        print(f"{'─' * 40}")

        pe = calculate_pe_valuation(ticker)
        if pe:
            print(f"  [P/E]   ratio={pe['pe_ratio']}  "
                  f"benchmark={pe['benchmark_pe']}  "
                  f"discount={pe['pe_discount']:.2%}  "
                  f"signal={pe['pe_signal']}")
        else:
            print(f"  [P/E]   FAIL — no data")
            all_passed = False

        dcf = calculate_dcf(ticker)
        if dcf:
            print(f"  [DCF]   intrinsic={dcf['intrinsic_value']}  "
                  f"price={dcf['current_price']}  "
                  f"MoS={dcf['margin_of_safety']:.2%}  "
                  f"signal={dcf['dcf_signal']}")
        else:
            print(f"  [DCF]   FAIL — no data")
            all_passed = False

        score = calculate_composite_score(ticker)
        if score:
            print(f"  [Score] {score['score']} / 100")
            for k, v in score['breakdown'].items():
                print(f"          {k:<20} {v:.2f} pts")
        else:
            print(f"  [Score] FAIL — no data")
            all_passed = False

    print(f"\n{'=' * 60}")
    print(f"  Result: {'ALL TESTS PASSED ✅' if all_passed else 'SOME TESTS FAILED ❌'}")
    print(f"{'=' * 60}\n")