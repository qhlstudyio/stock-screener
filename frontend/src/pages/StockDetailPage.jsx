// src/pages/StockDetailPage.jsx
// Individual stock fundamental analysis dashboard.
//
// Layout uses card-grid-2 (two-column) for sections where cards pair naturally:
//   Valuation   : Score Breakdown (left) + DCF Scenarios (right)
//   Financials  : Profitability + Returns  /  Leverage + Efficiency
//   Risk        : Risk Metrics (left)      + Returns vs SPY (right)
//   Analyst / Raw Data: full-width (fewer cards, enough data)

import { useState, useEffect }    from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getStock }               from '../api/stocks.js'
import { fmtPct, fmtX, fmtCap, fmtScore, fmtDecimal } from '../utils/formatters.js'
import Card      from '../components/common/Card.jsx'
import Badge     from '../components/common/Badge.jsx'
import MetricRow  from '../components/common/MetricRow.jsx'
import PriceChart from '../components/common/PriceChart.jsx'


// ── Helpers ────────────────────────────────────────────────────────────────────

const p = fmtPct

function signCls(v) {
  if (v == null) return ''
  return v > 0 ? 'text-positive' : 'text-negative'
}


// ── Small shared pieces ────────────────────────────────────────────────────────

function SectionTitle({ children }) {
  return <h2 className="section-title">{children}</h2>
}

function KpiCard({ label, value, sub, signal }) {
  return (
    <div className="kpi-card">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value num">{value ?? '—'}</span>
      {sub    && <span className="kpi-sub">{sub}</span>}
      {signal && <Badge signal={signal} />}
    </div>
  )
}

function ScoreBar({ label, score, max }) {
  const fill = score != null ? Math.min(score / max, 1) * 100 : 0
  return (
    <div className="score-bar-row">
      <span className="score-bar-label">{label}</span>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${fill}%` }} />
      </div>
      <span className="score-bar-val num">
        {score != null ? score.toFixed(1) : '—'} / {max}
      </span>
    </div>
  )
}


// ── Section: Overview ──────────────────────────────────────────────────────────

function OverviewSection({ stock }) {
  return (
    <>
      {/* Company identity */}
      <div className="company-header">
        <div className="company-header-left">
          <h1 className="company-name">{stock.company_name ?? stock.ticker}</h1>
          <div className="company-meta">
            <span className="num">{stock.ticker}</span>
            {stock.exchange && <><span className="meta-dot">·</span><span>{stock.exchange}</span></>}
            {stock.sector   && <><span className="meta-dot">·</span><span>{stock.sector}</span></>}
          </div>
          {stock.industry && <div className="company-industry">{stock.industry}</div>}
        </div>
        <div className="company-header-right">
          <span className="headline-score num">{fmtScore(stock.score)}</span>
          <span className="headline-score-label">Score / 100</span>
        </div>
      </div>

      {/* 4 KPI cards */}
      <div className="kpi-row">
        <KpiCard
          label="Trailing P/E"
          value={fmtX(stock.pe_ratio)}
          sub={stock.pe_discount != null ? `${p(stock.pe_discount, 1)} vs sector` : null}
          signal={stock.pe_signal}
        />
        <KpiCard
          label="DCF (Base Case)"
          value={stock.intrinsic_value != null ? `$${stock.intrinsic_value.toFixed(0)}` : null}
          sub={stock.margin_of_safety  != null ? `${p(stock.margin_of_safety, 1)} MoS`  : null}
          signal={stock.dcf_signal}
        />
        <KpiCard
          label="Graham Number"
          value={stock.graham_number    != null ? `$${stock.graham_number.toFixed(0)}`       : null}
          sub={stock.margin_to_graham   != null ? `${p(stock.margin_to_graham, 1)} to Graham` : null}
          signal={stock.graham_signal}
        />
        <KpiCard
          label="Market Cap"
          value={fmtCap(stock.market_cap)}
          sub={stock.current_price != null ? `Price: $${stock.current_price}` : null}
        />
      </div>

      {/* Edge-case alerts */}
      {stock.edge_case_flags?.length > 0 && (
        <div className="alert-list">
          {stock.edge_case_flags.map(f => (
            <div key={f.code} className={`alert alert--${f.severity}`}>
              <span className="alert-icon">{f.severity === 'warning' ? '⚠' : 'ℹ'}</span>
              <div>
                <div className="alert-title">{f.title}</div>
                <div className="alert-msg">{f.message}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Price chart vs SPY — uses historical stock_prices data */}
      <div className="overview-chart">
        <Card title={`${stock.ticker} vs SPY — Price Return`}>
          <PriceChart ticker={stock.ticker} showSpy={true} defaultPeriod="1y" />
        </Card>
      </div>
    </>
  )
}


// ── Section: Valuation ─────────────────────────────────────────────────────────
// Layout: Score (left) | DCF scenarios (right) — Graham below full-width

const SCORE_DEFS = [
  { key: 'gross_margin',  label: 'Gross Margin',  max: 15 },
  { key: 'profit_margin', label: 'Profit Margin', max: 15 },
  { key: 'roe',           label: 'ROE',           max: 20 },
  { key: 'debt_ratio',    label: 'Debt Ratio',    max: 15 },
  { key: 'pe_valuation',  label: 'P/E Valuation', max: 15 },
  { key: 'dcf_valuation', label: 'DCF Valuation', max: 20 },
]

const DCF_LABELS = { bear: '📉 Bear', base: '📊 Base', bull: '📈 Bull' }

function ValuationSection({ stock }) {
  const bd  = stock.score_breakdown
  const dcf = stock.dcf_scenarios

  return (
    <>
      {/* Score + DCF side-by-side; Score full-width when DCF unavailable */}
      <div className={dcf ? 'card-grid-2' : ''}>
        <Card title="Composite Score">
          <div className="total-score num">
            {fmtScore(stock.score)}
            <span className="total-score-denom"> / 100</span>
          </div>
          <div className="score-bar-list">
            {SCORE_DEFS.map(({ key, label, max }) => (
              <ScoreBar key={key} label={label} score={bd?.[key]} max={max} />
            ))}
          </div>
          <p className="card-note">Score is a sorting tool, not an investment recommendation.</p>
        </Card>

        {dcf && (
          <Card title="DCF Valuation — Three Scenarios">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>Growth</th>
                    <th>Intrinsic</th>
                    <th>Margin of Safety</th>
                    <th>Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {['bear', 'base', 'bull'].map(k => {
                    const s = dcf[k]
                    if (!s) return null
                    return (
                      <tr key={k}>
                        <td>{DCF_LABELS[k]}</td>
                        <td className="num">{p(s.growth_rate, 0)}</td>
                        <td className="num">${s.intrinsic_value?.toFixed(2)}</td>
                        <td className={`num ${signCls(s.margin_of_safety)}`}>
                          {p(s.margin_of_safety, 1)}
                        </td>
                        <td><Badge signal={s.dcf_signal} /></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="card-note">
              Discount rate 10% · Terminal rate 3% · 10-year projection ·
              Current price: <span className="num">${stock.current_price}</span>
            </p>
          </Card>
        )}
      </div>

      {/* Graham Number — full width */}
      <Card title="Graham Number">
        <div className="graham-grid">
          {[
            ['Graham Number',    stock.graham_number        != null ? `$${stock.graham_number.toFixed(2)}`       : null],
            ['Current Price',    stock.current_price        != null ? `$${stock.current_price}`                  : null],
            ['Margin to Graham', stock.margin_to_graham     != null ? p(stock.margin_to_graham, 1)               : null],
            ['Book Value/Share', stock.book_value_per_share != null ? `$${stock.book_value_per_share.toFixed(2)}` : null],
          ].map(([label, val]) => (
            <div key={label} className="graham-item">
              <span className="graham-label">{label}</span>
              <span className="graham-value num">{val ?? '—'}</span>
            </div>
          ))}
        </div>
        {stock.graham_signal && <div style={{ marginTop: 12 }}><Badge signal={stock.graham_signal} /></div>}
        <p className="card-note">
          √(22.5 × EPS × Book Value/Share). Requires positive EPS and book value.
        </p>
      </Card>
    </>
  )
}


// ── Section: Financials ────────────────────────────────────────────────────────
// Layout: Profitability | Return Metrics
//         Leverage      | Efficiency

function FinancialsSection({ stock }) {
  const { roe, roa, roic } = stock
  return (
    <>
      <div className="card-grid-2">
        <Card title="Profitability Margins">
          <MetricRow label="Gross Margin"     value={p(stock.gross_margin)}     bar={stock.gross_margin}     barMax={0.80} />
          <MetricRow label="Operating Margin" value={p(stock.operating_margin)} bar={stock.operating_margin} barMax={0.40} />
          <MetricRow label="Net Margin"       value={p(stock.profit_margin)}    bar={stock.profit_margin}    barMax={0.35} />
          <MetricRow label="FCF Margin"       value={p(stock.fcf_margin)}       bar={stock.fcf_margin}       barMax={0.35} />
          <MetricRow label="FCF Conversion"   value={stock.fcf_conversion != null ? fmtDecimal(stock.fcf_conversion, 2) + 'x' : '—'} />
        </Card>

        <Card title="Return Metrics">
          {/* Bars capped so buyback-inflated ROE doesn't break the bar UI */}
          <MetricRow label="ROE"  value={p(roe)}  bar={Math.min(roe  ?? 0, 0.60)} barMax={0.60} />
          <MetricRow label="ROA"  value={p(roa)}  bar={Math.min(roa  ?? 0, 0.25)} barMax={0.25} />
          <MetricRow label="ROIC" value={p(roic)} bar={Math.min(roic ?? 0, 0.30)} barMax={0.30} />
        </Card>
      </div>

      <div className="card-grid-2">
        <Card title="Leverage & Liquidity">
          <MetricRow label="Debt / Assets"     value={p(stock.debt_ratio)} />
          <MetricRow label="Debt / Equity"     value={stock.d_e_ratio         != null ? fmtX(stock.d_e_ratio, 2)             : '—'} />
          <MetricRow label="Interest Coverage" value={stock.interest_coverage != null ? fmtX(stock.interest_coverage, 1)     : '—'} />
          <MetricRow label="Current Ratio"     value={stock.current_ratio     != null ? fmtDecimal(stock.current_ratio, 2) + 'x' : '—'} />
        </Card>

        <Card title="Efficiency">
          <MetricRow label="R&D / Revenue"      value={p(stock.rd_ratio)} />
          <MetricRow label="CapEx / Revenue"    value={p(stock.capex_ratio)} />
          <MetricRow label="Revenue / Employee" value={fmtCap(stock.revenue_per_employee)} />
          <MetricRow label="EV / EBITDA"        value={fmtX(stock.ev_ebitda)} />
          <MetricRow label="EV / Revenue"       value={fmtX(stock.ev_revenue)} />
        </Card>
      </div>
    </>
  )
}


// ── Section: Risk ──────────────────────────────────────────────────────────────
// Layout: Risk Metrics (left) | Returns vs SPY (right)

const PERIODS = [
  { label: '1 Month',  retKey: 'return_1m', spyKey: 'vs_spy_1m' },
  { label: '3 Months', retKey: 'return_3m', spyKey: 'vs_spy_3m' },
  { label: '6 Months', retKey: 'return_6m', spyKey: 'vs_spy_6m' },
  { label: '1 Year',   retKey: 'return_1y', spyKey: 'vs_spy_1y' },
]

function RiskSection({ stock }) {
  return (
    <div className="card-grid-2">
      <Card title="Risk Metrics">
        <MetricRow label="Beta (calculated)" value={fmtDecimal(stock.beta, 2)} />
        <MetricRow label="Beta (yfinance)"   value={fmtDecimal(stock.beta_yf, 2)} />
        <MetricRow label="R² vs SPY"         value={p(stock.r_squared)} />
        <MetricRow label="Volatility (ann.)" value={p(stock.volatility)} />
        <MetricRow label="Sharpe Ratio"      value={fmtDecimal(stock.sharpe, 2)} />
        <MetricRow label="Alpha (ann.)"      value={p(stock.alpha)} />
        <MetricRow label="Max Drawdown"      value={p(stock.max_drawdown)} />
      </Card>

      <Card title="Price Returns vs S&P 500">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Stock</th>
                <th>vs SPY (excess)</th>
              </tr>
            </thead>
            <tbody>
              {PERIODS.map(({ label, retKey, spyKey }) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td className={`num ${signCls(stock[retKey])}`}>{p(stock[retKey])}</td>
                  <td className={`num ${signCls(stock[spyKey])}`}>{p(stock[spyKey])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="card-note">Calculated from daily price history vs SPY benchmark.</p>
        <p className="card-note" style={{ marginTop: 4 }}>
          📈 Price chart with SPY overlay — coming in M5.
        </p>
      </Card>
    </div>
  )
}


// ── Section: Analyst ───────────────────────────────────────────────────────────

const REC_MAP = {
  strong_buy:  'Strong Buy',   buy:         'Buy',
  hold:        'Hold',         sell:        'Sell',
  strong_sell: 'Strong Sell',  underperform:'Underperform',
}

function AnalystSection({ stock }) {
  const upside = (stock.target_mean_price && stock.current_price)
    ? (stock.target_mean_price / stock.current_price - 1) : null

  return (
    <Card title="Analyst Consensus">
      <MetricRow label="Mean Target Price"  value={stock.target_mean_price != null ? `$${stock.target_mean_price.toFixed(2)}`  : '—'} />
      <MetricRow label="High Target Price"  value={stock.target_high_price != null ? `$${stock.target_high_price.toFixed(2)}`  : '—'} />
      <MetricRow label="Low Target Price"   value={stock.target_low_price  != null ? `$${stock.target_low_price.toFixed(2)}`   : '—'} />
      <MetricRow label="Current Price"      value={stock.current_price     != null ? `$${stock.current_price}`                 : '—'} />
      <MetricRow label="Implied Upside"     value={<span className={signCls(upside)}>{p(upside)}</span>} />
      <MetricRow label="Analyst Coverage"   value={stock.analyst_count != null ? `${stock.analyst_count} analysts`            : '—'} />
      <MetricRow label="Recommendation"     value={REC_MAP[stock.recommendation_key] ?? stock.recommendation_key ?? '—'} />
      <p className="card-note">Consensus reflects current analyst coverage; refreshed quarterly.</p>
    </Card>
  )
}


// ── Section: Raw Data ──────────────────────────────────────────────────────────

const RAW_FIELDS = [
  ['Revenue',               'revenue',             'cap'],
  ['Net Income',            'net_income',           'cap'],
  ['Gross Profit',          'gross_profit',         'cap'],
  ['Operating Income',      'operating_income',     'cap'],
  ['Free Cash Flow',        'free_cash_flow',       'cap'],
  ['Total Assets',          'total_assets',         'cap'],
  ['Total Debt',            'total_debt',           'cap'],
  ["Shareholders' Equity",  'shareholders_equity',  'cap'],
  ['Current Assets',        'current_assets',       'cap'],
  ['Current Liabilities',   'current_liabilities',  'cap'],
  ['R&D Expense',           'research_development', 'cap'],
  ['Capital Expenditures',  'capital_expenditures', 'cap'],
  ['EPS (trailing)',        'eps',                  'usd'],
  ['EPS (forward)',         'forward_eps',          'usd'],
  ['Shares Outstanding',    'shares_outstanding',   'cap'],
  ['Enterprise Value',      'enterprise_value',     'cap'],
  ['EV / EBITDA',           'ev_ebitda',            'x1'],
  ['Forward P/E',           'forward_pe',           'x1'],
  ['Dividend Yield',        'dividend_yield',       'direct_pct'],
  ['Dividend Rate',         'dividend_rate',        'usd'],
  ['Payout Ratio',          'payout_ratio',         'pct'],
]

function rawFmt(v, fmt) {
  if (v == null) return '—'
  switch (fmt) {
    case 'cap':        return fmtCap(v)
    case 'pct':        return fmtPct(v)
    case 'direct_pct': return v.toFixed(2) + '%'
    case 'usd':        return `$${v.toFixed(2)}`
    case 'x1':         return fmtX(v)
    default:           return String(v)
  }
}

function RawDataSection({ stock }) {
  return (
    <Card title="Raw Financial Data">
      <div className="table-wrap">
        <table className="data-table data-table--raw">
          <tbody>
            {RAW_FIELDS.map(([label, key, fmt]) => (
              <tr key={key}>
                <td className="raw-label">{label}</td>
                <td className="raw-value num">{rawFmt(stock[key], fmt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="card-note">
        Source: yfinance · Most recent annual filing.
        Capital Expenditures are negative (yfinance cash-outflow convention).
      </p>
    </Card>
  )
}


// ── Loading & Error ────────────────────────────────────────────────────────────

function LoadingState({ ticker }) {
  return (
    <div className="detail-loading">
      <div className="spinner" />
      <span>Loading {ticker?.toUpperCase()}…</span>
    </div>
  )
}

function ErrorState({ error, ticker }) {
  const navigate = useNavigate()
  return (
    <div className="detail-error">
      <h2>Could not load {ticker?.toUpperCase()}</h2>
      <p>{error}</p>
      <button className="back-btn" onClick={() => navigate('/screening')}>
        ← Back to Screening
      </button>
    </div>
  )
}


// ── Page ───────────────────────────────────────────────────────────────────────

export default function StockDetailPage() {
  const { ticker }            = useParams()
  const [stock, setStock]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setStock(null)
    getStock(ticker.toUpperCase())
      .then(data => { setStock(data); setLoading(false) })
      .catch(err  => { setError(err.message); setLoading(false) })
  }, [ticker])

  if (loading) return <LoadingState ticker={ticker} />
  if (error)   return <ErrorState error={error} ticker={ticker} />
  if (!stock)  return null

  return (
    <div className="detail-page">

      <section id="overview" className="detail-section detail-section--first">
        <OverviewSection stock={stock} />
      </section>

      <section id="valuation" className="detail-section">
        <SectionTitle>Valuation</SectionTitle>
        <ValuationSection stock={stock} />
      </section>

      <section id="financials" className="detail-section">
        <SectionTitle>Financials</SectionTitle>
        <FinancialsSection stock={stock} />
      </section>

      <section id="risk" className="detail-section">
        <SectionTitle>Risk &amp; Returns</SectionTitle>
        <RiskSection stock={stock} />
      </section>

      <section id="analyst" className="detail-section">
        <SectionTitle>Analyst Consensus</SectionTitle>
        <AnalystSection stock={stock} />
      </section>

      <section id="raw-data" className="detail-section">
        <SectionTitle>Raw Financial Data</SectionTitle>
        <RawDataSection stock={stock} />
      </section>

    </div>
  )
}
