# analysis/risk_metrics.py
# Statistical risk metrics calculated from stock_prices table.
#
# Performance optimization (M5):
#   SPY prices are loaded from the DB exactly once per server lifetime and
#   cached at module level. Without this, every call to calculate_all_risk_metrics
#   triggers a full DB query (~1260 rows) for SPY — repeated 83 times when
#   loading the Information Technology sector.
#
# Main entry point:
#   calculate_all_risk_metrics(ticker) → dict | None
#
# Constants:
#   RISK_FREE_RATE  — annualised, update periodically to reflect current
#                     10-year US Treasury yield. Default: 4.5% (mid-2026).
#   BETA_WINDOW     — trading days used for Beta / Alpha / Sharpe. Default: 252.
#   TRADING_DAYS    — standard annualisation factor. Always 252.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data.db import get_stock_prices


# ── Constants ──────────────────────────────────────────────────────────────────

RISK_FREE_RATE = 0.045   # 4.5% — approximate US 10-year Treasury yield, mid-2026
BETA_WINDOW    = 252     # trading days (~1 year)
TRADING_DAYS   = 252     # annualisation factor (do not change)
BENCHMARK      = 'SPY'   # market benchmark ticker

RETURN_WINDOWS = {
    '1m':  21,
    '3m':  63,
    '6m':  126,
    '1y':  252,
}


# ── SPY price cache ────────────────────────────────────────────────────────────
# SPY prices are identical for every stock calculation in a given session.
# Loading them once and reusing saves one full DB round-trip per ticker —
# the difference between 83 DB queries and 1 when screening a large sector.
# The cache is reset only on server restart (acceptable: daily_updater adds
# at most one new row per day, and overnight restarts clear the cache anyway).

_spy_prices_cache: pd.Series | None = None


def _get_spy_prices() -> pd.Series | None:
    """
    Return the SPY closing price series, loading from DB on first call only.
    Subsequent calls return the in-memory cached Series instantly.
    """
    global _spy_prices_cache
    if _spy_prices_cache is None:
        _spy_prices_cache = _load_prices(BENCHMARK)
    return _spy_prices_cache


def invalidate_spy_cache() -> None:
    """
    Force SPY prices to be reloaded on the next call.
    Call this from daily_updater.py after updating stock_prices if needed.
    In practice a server restart achieves the same effect.
    """
    global _spy_prices_cache
    _spy_prices_cache = None


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_prices(ticker: str) -> pd.Series | None:
    """
    Load the full closing price series for a ticker.
    Returns a pd.Series indexed by date, or None if no data.
    """
    df = get_stock_prices(ticker)
    if df is None or df.empty:
        return None
    return df.set_index('date')['close'].sort_index()


def _daily_returns(prices: pd.Series) -> pd.Series:
    """Compute daily percentage returns from a closing price series."""
    return prices.pct_change().dropna()


def _align(s1: pd.Series, s2: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Align two return series on their common dates."""
    common = s1.index.intersection(s2.index)
    return s1.loc[common], s2.loc[common]


# ── Core calculations ──────────────────────────────────────────────────────────

def _beta_and_r2(
    stock_ret: pd.Series,
    spy_ret:   pd.Series,
) -> tuple[float | None, float | None]:
    """
    Return (beta, r_squared) using the last BETA_WINDOW aligned trading days.

    Beta    = Cov(stock, SPY) / Var(SPY)
    R²      = Corr(stock, SPY)²
    """
    window       = min(BETA_WINDOW, len(stock_ret))
    stock_window = stock_ret.iloc[-window:]
    spy_window   = spy_ret.iloc[-window:]

    if len(stock_window) < 30:
        return None, None

    spy_var = spy_window.var()
    if spy_var == 0:
        return None, None

    beta        = stock_window.cov(spy_window) / spy_var
    correlation = stock_window.corr(spy_window)
    r_squared   = correlation ** 2

    return round(float(beta), 3), round(float(r_squared), 3)


def _annualised_volatility(stock_ret: pd.Series) -> float | None:
    """Annualised standard deviation of daily returns."""
    window = min(BETA_WINDOW, len(stock_ret))
    ret    = stock_ret.iloc[-window:]
    if len(ret) < 30:
        return None
    vol = ret.std() * (TRADING_DAYS ** 0.5)
    return round(float(vol), 4)


def _annualised_return(stock_ret: pd.Series, window: int) -> float | None:
    """Compound annualised return over the last `window` trading days."""
    ret = stock_ret.iloc[-window:]
    if len(ret) < 10:
        return None
    ann = (1 + ret.mean()) ** TRADING_DAYS - 1
    return float(ann)


def _sharpe(
    ann_return: float | None,
    volatility: float | None,
    risk_free:  float = RISK_FREE_RATE,
) -> float | None:
    """Sharpe Ratio = (annualised_return - risk_free) / annualised_volatility"""
    if ann_return is None or volatility is None or volatility == 0:
        return None
    return round(float((ann_return - risk_free) / volatility), 3)


def _alpha(
    ann_return:     float | None,
    beta:           float | None,
    spy_ann_return: float | None,
    risk_free:      float = RISK_FREE_RATE,
) -> float | None:
    """Jensen's Alpha = actual_return - (risk_free + beta × (spy_return - risk_free))"""
    if any(v is None for v in (ann_return, beta, spy_ann_return)):
        return None
    expected = risk_free + beta * (spy_ann_return - risk_free)
    return round(float(ann_return - expected), 4)


def _max_drawdown(prices: pd.Series) -> float | None:
    """Maximum peak-to-trough decline. Returns a negative number."""
    if prices is None or len(prices) < 10:
        return None
    rolling_peak = prices.cummax()
    drawdown     = (prices - rolling_peak) / rolling_peak
    return round(float(drawdown.min()), 4)


def _price_returns(
    stock_prices: pd.Series,
    spy_prices:   pd.Series | None,
) -> dict:
    """1M / 3M / 6M / 1Y price returns + vs-SPY relative performance."""
    result = {}
    for label, days in RETURN_WINDOWS.items():
        if len(stock_prices) >= days + 1:
            ret = (stock_prices.iloc[-1] - stock_prices.iloc[-(days + 1)]) \
                  / stock_prices.iloc[-(days + 1)]
            result[f'return_{label}'] = round(float(ret), 4)
        else:
            result[f'return_{label}'] = None

        if spy_prices is not None and len(spy_prices) >= days + 1:
            spy_ret       = (spy_prices.iloc[-1] - spy_prices.iloc[-(days + 1)]) \
                            / spy_prices.iloc[-(days + 1)]
            stock_ret_val = result.get(f'return_{label}')
            result[f'vs_spy_{label}'] = (
                round(float(stock_ret_val - spy_ret), 4)
                if stock_ret_val is not None else None
            )
        else:
            result[f'vs_spy_{label}'] = None

    return result


# ── Main entry point ───────────────────────────────────────────────────────────

def calculate_all_risk_metrics(
    ticker:    str,
    risk_free: float = RISK_FREE_RATE,
) -> dict | None:
    """
    Calculate all risk metrics for a ticker in a single pass.

    SPY prices come from the module-level cache (_get_spy_prices), so they
    are loaded from the DB at most once per server process regardless of how
    many stocks are being calculated simultaneously.

    Returns None if fewer than 30 days of price data exist.
    """
    stock_prices = _load_prices(ticker)
    spy_prices   = _get_spy_prices()          # ← cached; zero DB cost on repeat calls

    if stock_prices is None or len(stock_prices) < 30:
        return None

    stock_ret = _daily_returns(stock_prices)

    spy_ret = None
    if spy_prices is not None and not spy_prices.empty:
        spy_ret_full             = _daily_returns(spy_prices)
        stock_ret_aligned, spy_ret = _align(stock_ret, spy_ret_full)
    else:
        stock_ret_aligned = stock_ret

    beta, r_squared = _beta_and_r2(stock_ret_aligned, spy_ret) \
        if spy_ret is not None else (None, None)

    volatility  = _annualised_volatility(stock_ret)
    ann_ret     = _annualised_return(stock_ret_aligned, BETA_WINDOW)
    spy_ann_ret = _annualised_return(spy_ret, BETA_WINDOW) if spy_ret is not None else None

    sharpe  = _sharpe(ann_ret, volatility, risk_free)
    alpha   = _alpha(ann_ret, beta, spy_ann_ret, risk_free)
    max_dd  = _max_drawdown(stock_prices)
    returns = _price_returns(stock_prices, spy_prices)

    return {
        'beta':          beta,
        'r_squared':     r_squared,
        'volatility':    volatility,
        'sharpe':        sharpe,
        'alpha':         alpha,
        'max_drawdown':  max_dd,
        **returns,
        'current_price': round(float(stock_prices.iloc[-1]), 2),
        'data_days':     len(stock_prices),
        'risk_free_rate': risk_free,
    }


# ── Test block ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':

    test_tickers = ['MMM', 'ABBV', 'ABT']

    print("=" * 65)
    print("risk_metrics.py — test run")
    print("=" * 65)

    for ticker in test_tickers:
        print(f"\n{'─' * 50}")
        print(f"  {ticker}")
        print(f"{'─' * 50}")

        result = calculate_all_risk_metrics(ticker)
        if result is None:
            print("  No data — run bootstrap first")
            continue

        def _pct(v):  return f"{v:.2%}"   if v is not None else "N/A"
        def _x(v):    return f"{v:.2f}x"  if v is not None else "N/A"
        def _f(v):    return f"{v:.3f}"   if v is not None else "N/A"

        rows = [
            ("Beta (252d)",       _x(result['beta'])),
            ("R² vs SPY",        _pct(result['r_squared'])),
            ("Volatility (ann.)", _pct(result['volatility'])),
            ("Sharpe Ratio",      _f(result['sharpe'])),
            ("Alpha (ann.)",      _pct(result['alpha'])),
            ("Max Drawdown",      _pct(result['max_drawdown'])),
            ("1Y Return",         _pct(result['return_1y'])),
            ("1Y vs SPY",         _pct(result['vs_spy_1y'])),
            ("Current Price",     f"${result['current_price']}"),
        ]
        for label, value in rows:
            print(f"  {label:<25} {value}")

    print(f"\n{'=' * 65}\n")