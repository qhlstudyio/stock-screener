# analysis/screener.py
# Aggregates metrics and valuation for a list of tickers.
# Supports filtering and sorting for the UI layer.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from analysis.metrics import calculate_all_metrics
from analysis.valuation import calculate_pe_valuation, calculate_dcf, calculate_composite_score


# ---------------------------------------------------------------------------
# Part 1: Single stock profile builder
# ---------------------------------------------------------------------------

def build_stock_profile(ticker):
    """
    Build a complete flat profile for one ticker by combining:
      - Raw metrics   (metrics.py)
      - P/E valuation (valuation.py)
      - DCF valuation (valuation.py)
      - Composite score (valuation.py)

    Returns a flat dict ready for DataFrame conversion.
    Returns None if no data is available for the ticker.
    """
    metrics = calculate_all_metrics(ticker)
    if not metrics:
        return None

    pe_val  = calculate_pe_valuation(ticker)
    dcf_val = calculate_dcf(ticker)
    score   = calculate_composite_score(ticker)

    return {
        # --- Identity ---
        'ticker':           ticker,

        # --- Raw metrics (shown directly in UI) ---
        'gross_margin':     metrics.get('gross_margin'),
        'profit_margin':    metrics.get('profit_margin'),
        'roe':              metrics.get('roe'),
        'debt_ratio':       metrics.get('debt_ratio'),
        'pe_ratio':         metrics.get('pe_ratio'),
        'eps':              metrics.get('eps'),
        'market_cap':       metrics.get('market_cap'),
        'revenue':          metrics.get('revenue'),
        'net_income':       metrics.get('net_income'),
        'free_cash_flow':   metrics.get('free_cash_flow'),

        # --- P/E valuation ---
        'pe_discount':      pe_val.get('pe_discount')  if pe_val  else None,
        'pe_signal':        pe_val.get('pe_signal')    if pe_val  else None,

        # --- DCF valuation ---
        'intrinsic_value':  dcf_val.get('intrinsic_value')  if dcf_val else None,
        'current_price':    dcf_val.get('current_price')    if dcf_val else None,
        'margin_of_safety': dcf_val.get('margin_of_safety') if dcf_val else None,
        'dcf_signal':       dcf_val.get('dcf_signal')       if dcf_val else None,

        # --- Composite score ---
        'score':            score.get('score')     if score else None,
        'score_breakdown':  score.get('breakdown') if score else None,
    }


# ---------------------------------------------------------------------------
# Part 2: Batch screener
# ---------------------------------------------------------------------------

def screen_stocks(tickers=None, filters=None, sort_by='score', ascending=False):
    """
    Build profiles for all tickers, apply optional filters, then sort.

    Parameters
    ----------
    tickers : list[str] | None
        Ticker symbols to analyse.
        Falls back to config.ALL_TICKERS when None.

    filters : dict | None
        Supported keys (all optional):
            min_score        (float) minimum composite score
            max_pe           (float) maximum P/E ratio
            min_roe          (float) minimum ROE  e.g. 0.15 = 15%
            max_debt_ratio   (float) maximum debt ratio  e.g. 0.50 = 50%
            min_profit_margin(float) minimum profit margin

    sort_by   : str   field name to sort by (default: 'score')
    ascending : bool  True = lowest first, False = highest first (default)

    Returns
    -------
    list[dict]  filtered and sorted profiles
    """
    if tickers is None:
        tickers = config.ALL_TICKERS

    if filters is None:
        filters = {}

    # --- Build profiles ---
    profiles = []
    failed   = []

    for ticker in tickers:
        profile = build_stock_profile(ticker)
        if profile:
            profiles.append(profile)
        else:
            failed.append(ticker)

    if failed:
        print(f"  ⚠️  No data available for: {', '.join(failed)}")

    # --- Apply filters ---
    def passes(p):
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
        return True

    filtered = [p for p in profiles if passes(p)]

    # --- Sort (None values always go to the bottom) ---
    filtered.sort(
        key=lambda x: (
            x.get(sort_by) is not None,   # False sorts before True → Nones sink
            x.get(sort_by) or 0
        ),
        reverse=not ascending
    )

    return filtered


# ---------------------------------------------------------------------------
# Part 3: Preset groups (for UI group selector)
# ---------------------------------------------------------------------------

def get_preset_groups():
    """
    Predefined stock groups for the UI multi-select.
    The UI merges selected groups and deduplicates before calling screen_stocks().

    Returns dict[str, list[str]]
    """
    return {
        'Default List':   config.ALL_TICKERS,
        'Tech Giants':    ['AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA'],
        'Semiconductors': ['NVDA', 'AMD', 'INTC', 'QCOM', 'TSM'],
        'Value Stocks':   ['BRK-B', 'JPM', 'JNJ', 'PG', 'KO'],
    }


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------

if __name__ == '__main__':

    print("=" * 60)
    print("screener.py — test run")
    print("=" * 60)

    all_passed = True

    # --- Test 1: single profile ---
    print("\n[Test 1] build_stock_profile('AAPL')")
    profile = build_stock_profile('AAPL')
    if profile and profile.get('score') is not None:
        print(f"  ticker        : {profile['ticker']}")
        print(f"  score         : {profile['score']}")
        print(f"  gross_margin  : {profile['gross_margin']:.2%}")
        print(f"  roe           : {profile['roe']:.2%}")
        print(f"  pe_signal     : {profile['pe_signal']}")
        print(f"  dcf_signal    : {profile['dcf_signal']}")
        print(f"  PASS ✅")
    else:
        print(f"  FAIL ❌ — profile returned None or missing score")
        all_passed = False

    # --- Test 2: screen all default tickers, no filters ---
    print("\n[Test 2] screen_stocks() — no filters, sort by score")
    results = screen_stocks()
    if results:
        print(f"  {len(results)} stocks returned")
        for r in results:
            print(f"  {r['ticker']:<8} score={r['score']:<6} "
                  f"pe={r['pe_ratio']:<7.2f} "
                  f"roe={r['roe']:.2%}")
        print(f"  PASS ✅")
    else:
        print(f"  FAIL ❌ — empty results")
        all_passed = False

    # --- Test 3: screen with filters ---
    print("\n[Test 3] screen_stocks() — min_score=55, max_pe=35")
    filtered = screen_stocks(
        filters={'min_score': 55, 'max_pe': 35}
    )
    print(f"  {len(filtered)} stocks passed filters:")
    for r in filtered:
        print(f"  {r['ticker']:<8} score={r['score']:<6} pe={r['pe_ratio']:.2f}")
    print(f"  PASS ✅" if isinstance(filtered, list) else "  FAIL ❌")

    # --- Test 4: custom ticker list ---
    print("\n[Test 4] screen_stocks(['AAPL', 'MSFT'], sort_by='roe')")
    custom = screen_stocks(tickers=['AAPL', 'MSFT'], sort_by='roe')
    if custom and len(custom) == 2:
        for r in custom:
            print(f"  {r['ticker']:<8} roe={r['roe']:.2%}")
        print(f"  PASS ✅")
    else:
        print(f"  FAIL ❌")
        all_passed = False

    # --- Test 5: preset groups ---
    print("\n[Test 5] get_preset_groups()")
    groups = get_preset_groups()
    if groups and 'Tech Giants' in groups:
        for name, tickers in groups.items():
            print(f"  {name:<20} {tickers}")
        print(f"  PASS ✅")
    else:
        print(f"  FAIL ❌")
        all_passed = False

    print(f"\n{'=' * 60}")
    print(f"  Result: {'ALL TESTS PASSED ✅' if all_passed else 'SOME TESTS FAILED ❌'}")
    print(f"{'=' * 60}\n")