# api/schemas.py
# Pydantic response models for every API endpoint.

from __future__ import annotations
from pydantic import BaseModel, ConfigDict


# ── Nested building blocks ─────────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    gross_margin:  float | None = None
    profit_margin: float | None = None
    roe:           float | None = None
    debt_ratio:    float | None = None
    pe_valuation:  float | None = None
    dcf_valuation: float | None = None
    model_config = ConfigDict(extra="ignore")


class DcfScenario(BaseModel):
    growth_rate:      float | None = None
    intrinsic_value:  float | None = None
    current_price:    float | None = None
    margin_of_safety: float | None = None
    dcf_signal:       str   | None = None
    model_config = ConfigDict(extra="ignore")


class DcfScenarios(BaseModel):
    bear: DcfScenario | None = None
    base: DcfScenario | None = None
    bull: DcfScenario | None = None
    model_config = ConfigDict(extra="ignore")


class EdgeCaseFlag(BaseModel):
    code:     str
    severity: str
    metric:   str
    title:    str
    message:  str
    model_config = ConfigDict(extra="ignore")


# ── Search autocomplete ────────────────────────────────────────────────────────

class TickerItem(BaseModel):
    ticker:       str
    company_name: str  | None = None
    sector:       str  | None = None
    is_benchmark: bool        = False


# ── Historical price point ─────────────────────────────────────────────────────

class PricePoint(BaseModel):
    """One daily close price. Used by the price chart endpoint."""
    date:   str            # YYYY-MM-DD
    close:  float
    volume: int | None = None


# ── Main stock profile ─────────────────────────────────────────────────────────

class StockProfile(BaseModel):
    """
    Complete fundamental analysis profile for one stock.
    Null fields mean the data point is unavailable — display as '—', never as 0.

    Unit conventions:
      Margins / ratios  → decimal  (0.25 = 25%)
      dividend_yield    → percent  (0.81 = 0.81%)  ← yfinance quirk
      Prices            → USD per share
    """
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    ticker:       str
    company_name: str | None = None
    exchange:     str | None = None
    sector:       str | None = None
    industry:     str | None = None

    score:           float          | None = None
    score_breakdown: ScoreBreakdown | None = None

    gross_margin:     float | None = None
    operating_margin: float | None = None
    profit_margin:    float | None = None
    fcf_margin:       float | None = None

    roe:  float | None = None
    roa:  float | None = None
    roic: float | None = None

    debt_ratio:        float | None = None
    d_e_ratio:         float | None = None
    interest_coverage: float | None = None
    current_ratio:     float | None = None

    fcf_conversion:       float | None = None
    capex_ratio:          float | None = None
    rd_ratio:             float | None = None
    revenue_per_employee: float | None = None

    market_cap:         float | None = None
    enterprise_value:   float | None = None
    ev_ebitda:          float | None = None
    ev_revenue:         float | None = None
    pe_ratio:           float | None = None
    forward_pe:         float | None = None
    eps:                float | None = None
    forward_eps:        float | None = None
    shares_outstanding: float | None = None

    revenue:              float | None = None
    net_income:           float | None = None
    gross_profit:         float | None = None
    operating_income:     float | None = None
    free_cash_flow:       float | None = None
    total_assets:         float | None = None
    total_debt:           float | None = None
    shareholders_equity:  float | None = None
    current_assets:       float | None = None
    current_liabilities:  float | None = None
    research_development: float | None = None
    capital_expenditures: float | None = None

    dividend_yield: float | None = None
    dividend_rate:  float | None = None
    payout_ratio:   float | None = None

    beta_yf: float | None = None

    target_mean_price:  float | None = None
    target_high_price:  float | None = None
    target_low_price:   float | None = None
    analyst_count:      int   | None = None
    recommendation_key: str   | None = None

    pe_discount: float | None = None
    pe_signal:   str   | None = None

    intrinsic_value:  float | None = None
    current_price:    float | None = None
    margin_of_safety: float | None = None
    dcf_signal:       str   | None = None

    dcf_scenarios: DcfScenarios | None = None

    graham_number:        float | None = None
    margin_to_graham:     float | None = None
    graham_signal:        str   | None = None
    book_value_per_share: float | None = None

    beta:         float | None = None
    r_squared:    float | None = None
    volatility:   float | None = None
    sharpe:       float | None = None
    alpha:        float | None = None
    max_drawdown: float | None = None

    return_1m: float | None = None
    return_3m: float | None = None
    return_6m: float | None = None
    return_1y: float | None = None

    vs_spy_1m: float | None = None
    vs_spy_3m: float | None = None
    vs_spy_6m: float | None = None
    vs_spy_1y: float | None = None

    edge_case_flags: list[EdgeCaseFlag] = []
    ai_analysis: None = None


# ── Sector summary ─────────────────────────────────────────────────────────────

class SectorStats(BaseModel):
    sector:            str
    ticker_count:      int
    avg_pe_ratio:      float | None = None
    avg_gross_margin:  float | None = None
    avg_profit_margin: float | None = None
    avg_roe:           float | None = None
    median_market_cap: float | None = None
    model_config = ConfigDict(from_attributes=True, extra="ignore")


# ── S&P 500 membership ─────────────────────────────────────────────────────────

class MembershipEvent(BaseModel):
    ticker: str
    date:   str


class MembershipResponse(BaseModel):
    current_count:  int
    as_of:          str
    recent_added:   list[MembershipEvent]
    recent_removed: list[MembershipEvent]


# ── Health check ───────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:                str
    database:              str
    sp500_member_count:    int   | None = None
    latest_price_date:     str   | None = None
    latest_financial_date: str   | None = None
