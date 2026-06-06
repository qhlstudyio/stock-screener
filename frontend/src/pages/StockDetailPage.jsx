// src/pages/StockDetailPage.jsx
// Individual stock dashboard — chart-led redesign.
//
// Section order (matches navigation.js sectionIds):
//   overview     company header · price hero · 52W bar · KPI cards · alerts · price chart
//   valuation    score donut · valuation ruler · DCF scenarios · graham · multiples
//   financials   profit waterfall · return metrics vs sector · health metrics
//   risk         returns vs SPY bars · risk radar · risk stat rows
//   analyst      price target bar · consensus details
//   raw-data     raw financial statement numbers (grouped by category)

import { useState, useEffect }    from 'react'
import { useParams, useNavigate } from 'react-router-dom'

import { getStock, getSectors }   from '../api/stocks.js'
import { usePriceMetrics }        from '../hooks/usePriceMetrics.js'
import { fmtPct, fmtX, fmtCap, fmtScore, fmtDecimal } from '../utils/formatters.js'

import Card        from '../components/common/Card.jsx'
import Badge       from '../components/common/Badge.jsx'
import MetricRow   from '../components/common/MetricRow.jsx'
import PriceChart  from '../components/common/PriceChart.jsx'

import ProfitWaterfall    from '../components/charts/ProfitWaterfall.jsx'
import ReturnMetricsChart from '../components/charts/ReturnMetricsChart.jsx'
import ScoreDonut         from '../components/charts/ScoreDonut.jsx'
import ValuationRuler     from '../components/charts/ValuationRuler.jsx'
import ReturnBars         from '../components/charts/ReturnBars.jsx'
import RiskRadar          from '../components/charts/RiskRadar.jsx'


// ── Tiny helpers ───────────────────────────────────────────────────────────────

const p = fmtPct

function signCls(v) {
  if (v == null) return ''
  return v > 0 ? 'text-positive' : 'text-negative'
}

function SectionTitle({ children }) {
  return <h2 className="section-title">{children}</h2>
}


// ── Price Hero ─────────────────────────────────────────────────────────────────

function PriceHero({ stock, metrics }) {
  const price  = stock.current_price
  const change = metrics?.dailyChange
  const pct    = metrics?.dailyChangePct
  const isPos  = change == null ? null : change >= 0

  return (
    <div className="price-hero">
      <span className="price-hero-value num">
        {price != null ? `$${price}` : '—'}
      </span>
      {change != null ? (
        <span className={`price-hero-change num ${isPos ? 'text-positive' : 'text-negative'}`}>
          {isPos ? '▲' : '▼'}&nbsp;
          {isPos ? '+' : ''}{change.toFixed(2)}&ensp;
          ({isPos ? '+' : ''}{(pct * 100).toFixed(2)}%)
        </span>
      ) : (
        price != null && <span className="price-hero-label">Most recent close</span>
      )}
    </div>
  )
}


// ── 52-Week Range Bar ──────────────────────────────────────────────────────────

function Week52Bar({ low, high, current }) {
  if (!low || !high || !current) return null
  const pct = Math.max(0, Math.min(100, ((current - low) / (high - low)) * 100))
  return (
    <div className="w52">
      <div className="w52-track">
        <div className="w52-fill"  style={{ width: `${pct}%` }} />
        <div className="w52-thumb" style={{ left:  `${pct}%` }} />
      </div>
      <div className="w52-labels">
        <span className="num">${low.toFixed(2)}</span>
        <span className="w52-center-label">52-Week Range</span>
        <span className="num">${high.toFixed(2)}</span>
      </div>
    </div>
  )
}


// ── Overview Section ───────────────────────────────────────────────────────────

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

function OverviewSection({ stock, metrics }) {
  return (
    <>
      {/* Company identity + price */}
      <div className="company-header">
        <div className="company-header-left">
          <h1 className="company-name">{stock.company_name ?? stock.ticker}</h1>
          <div className="company-meta">
            <span className="num">{stock.ticker}</span>
            {stock.exchange && <><span className="meta-dot">·</span><span>{stock.exchange}</span></>}
            {stock.sector   && <><span className="meta-dot">·</span><span>{stock.sector}</span></>}
          </div>
          {stock.industry && <div className="company-industry">{stock.industry}</div>}

          <PriceHero stock={stock} metrics={metrics} />
          <Week52Bar
            low={metrics?.week52Low}
            high={metrics?.week52High}
            current={stock.current_price}
          />
        </div>

        <div className="company-header-right">
          <span className="headline-score num">{fmtScore(stock.score)}</span>
          <span className="headline-score-label">Score / 100</span>
        </div>
      </div>

      {/* KPI cards */}
      <div className="kpi-row">
        <KpiCard
          label="Trailing P/E"
          value={fmtX(stock.pe_ratio)}
          sub={stock.pe_discount != null ? `${p(stock.pe_discount, 1)} vs sector` : null}
          signal={stock.pe_signal}
        />
        <KpiCard
          label="DCF (Base)"
          value={stock.intrinsic_value != null ? `$${stock.intrinsic_value.toFixed(0)}` : null}
          sub={stock.margin_of_safety  != null ? `${p(stock.margin_of_safety, 1)} MoS`  : null}
          signal={stock.dcf_signal}
        />
        <KpiCard
          label="Graham Number"
          value={stock.graham_number    != null ? `$${stock.graham_number.toFixed(0)}`        : null}
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

      {/* Price chart vs SPY */}
      <div className="overview-chart">
        <Card title={`${stock.ticker} vs SPY — Price Return`}>
          <PriceChart ticker={stock.ticker} showSpy defaultPeriod="1y" />
        </Card>
      </div>
    </>
  )
}


// ── Valuation Section ──────────────────────────────────────────────────────────

const DCF_SCENARIO_COLOR = { bear: 'var(--negative)', base: 'var(--text2)', bull: 'var(--positive)' }
const DCF_LABELS         = { bear: 'Bear',            base: 'Base',         bull: 'Bull'            }

function ValuationSection({ stock }) {
  const dcf = stock.dcf_scenarios

  // Frontend-computed multiples
  const ps            = stock.market_cap && stock.revenue
                          ? stock.market_cap / stock.revenue : null
  const pb            = stock.current_price && stock.book_value_per_share
                          ? stock.current_price / stock.book_value_per_share : null
  const earningsYield = stock.pe_ratio ? (1 / stock.pe_ratio) * 100 : null

  return (
    <>
      {/* Score donut + Valuation ruler */}
      <div className="card-grid-2">
        <Card title="Composite Score">
          <ScoreDonut score={stock.score} scoreBreakdown={stock.score_breakdown} />
          <p className="card-note" style={{ marginTop: 12 }}>
            Sorting tool only — not an investment recommendation.
          </p>
        </Card>

        <Card title="Valuation Ruler">
          <p className="card-sub-inline">
            Current price relative to intrinsic value estimates
          </p>
          <ValuationRuler stock={stock} />
        </Card>
      </div>

      {/* DCF scenarios */}
      {dcf && (
        <Card title="DCF Scenarios — Three Growth Assumptions">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Growth</th>
                  <th>Intrinsic Value</th>
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
                      <td style={{ color: DCF_SCENARIO_COLOR[k], fontWeight: 600 }}>
                        {DCF_LABELS[k]}
                      </td>
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

      {/* Graham + Valuation Multiples */}
      <div className="card-grid-2">
        <Card title="Graham Number">
          <div className="graham-grid">
            {[
              ['Graham Number',    stock.graham_number        != null ? `$${stock.graham_number.toFixed(2)}`        : null],
              ['Current Price',    stock.current_price        != null ? `$${stock.current_price}`                   : null],
              ['Margin to Graham', stock.margin_to_graham     != null ? p(stock.margin_to_graham, 1)                : null],
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

        <Card title="Valuation Multiples">
          <MetricRow label="Price / Sales (P/S)"
            value={ps != null ? `${ps.toFixed(2)}x` : '—'} />
          <MetricRow label="Price / Book (P/B)"
            value={pb != null ? `${pb.toFixed(2)}x` : '—'} />
          <MetricRow label="Earnings Yield"
            value={earningsYield != null ? `${earningsYield.toFixed(2)}%` : '—'} />
          <MetricRow label="EV / Revenue"
            value={stock.ev_revenue != null ? `${fmtDecimal(stock.ev_revenue, 1)}x` : '—'} />
          <MetricRow label="Forward P/E"
            value={stock.forward_pe != null ? fmtX(stock.forward_pe) : '—'} />
          <p className="card-note" style={{ marginTop: 12 }}>
            P/S and P/B derived from market cap, revenue, and book value.
            Earnings yield = 1 / trailing P/E.
          </p>
        </Card>
      </div>
    </>
  )
}


// ── Financials Section ─────────────────────────────────────────────────────────

function FinancialsSection({ stock, sectorStats }) {
  return (
    <>
      <Card title="Profit Waterfall">
        <p className="card-sub-inline">
          How much of each revenue dollar survives each cost layer — hover for definitions
        </p>
        <ProfitWaterfall stock={stock} />
      </Card>

      <div className="card-grid-2">
        <Card title="Return on Capital">
          <ReturnMetricsChart stock={stock} sectorStats={sectorStats} />
        </Card>

        <Card title="Leverage & Efficiency">
          <MetricRow label="Debt / Assets"      value={p(stock.debt_ratio)} />
          <MetricRow label="Debt / Equity"       value={stock.d_e_ratio        != null ? fmtX(stock.d_e_ratio, 2)              : '—'} />
          <MetricRow label="Interest Coverage"   value={stock.interest_coverage != null ? fmtX(stock.interest_coverage, 1)      : '—'} />
          <MetricRow label="Current Ratio"       value={stock.current_ratio     != null ? fmtDecimal(stock.current_ratio, 2) + 'x' : '—'} />
          <MetricRow label="FCF Conversion"      value={stock.fcf_conversion    != null ? fmtDecimal(stock.fcf_conversion, 2) + 'x' : '—'} />
          <MetricRow label="R&D / Revenue"       value={p(stock.rd_ratio)} />
          <MetricRow label="CapEx / Revenue"     value={p(stock.capex_ratio)} />
          <MetricRow label="Revenue / Employee"  value={fmtCap(stock.revenue_per_employee)} />
        </Card>
      </div>
    </>
  )
}


// ── Risk Section ───────────────────────────────────────────────────────────────

function RiskSection({ stock }) {
  return (
    <>
      <div className="card-grid-2">
        <Card title="Price Returns vs SPY">
          <ReturnBars stock={stock} />
        </Card>

        <Card title="Risk Profile">
          <RiskRadar stock={stock} />
        </Card>
      </div>

      <Card title="Risk Statistics">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
          <div>
            <MetricRow label="Beta (calculated)" value={fmtDecimal(stock.beta, 2)} />
            <MetricRow label="Beta (yfinance)"   value={fmtDecimal(stock.beta_yf, 2)} />
            <MetricRow label="R² vs SPY"         value={p(stock.r_squared)} />
            <MetricRow label="Volatility (ann.)" value={p(stock.volatility)} />
          </div>
          <div>
            <MetricRow label="Sharpe Ratio" value={fmtDecimal(stock.sharpe, 2)} />
            <MetricRow label="Alpha (ann.)" value={p(stock.alpha)} />
            <MetricRow label="Max Drawdown" value={p(stock.max_drawdown)} />
          </div>
        </div>
      </Card>
    </>
  )
}


// ── Analyst Section ────────────────────────────────────────────────────────────

function AnalystTargetBar({ stock }) {
  const {
    target_low_price:  low,
    target_high_price: high,
    target_mean_price: mean,
    current_price:     current,
  } = stock

  if (!low || !high) return null

  const range   = high - low
  const clamp   = v => Math.max(2, Math.min(98, v))
  const curPct  = current != null ? clamp((current - low) / range * 100) : null
  const meanPct = mean    != null ? clamp((mean    - low) / range * 100) : null
  const upside  = mean != null && current != null ? (mean / current - 1) : null

  return (
    <div className="atb">
      <div className="atb-track">
        {curPct  != null && <div className="atb-fill"             style={{ width: `${curPct}%` }} />}
        {curPct  != null && <div className="atb-pin atb-pin--cur" style={{ left:  `${curPct}%` }} />}
        {meanPct != null && <div className="atb-pin atb-pin--mean" style={{ left: `${meanPct}%` }} />}
      </div>
      <div className="atb-edges">
        <span><span className="num">${low.toFixed(0)}</span><span className="atb-edge-lbl"> Low</span></span>
        <span><span className="atb-edge-lbl">High </span><span className="num">${high.toFixed(0)}</span></span>
      </div>
      <div className="atb-stats">
        <div className="atb-stat">
          <div className="atb-stat-pip atb-stat-pip--cur" />
          <span className="atb-stat-key">Current</span>
          <span className="num atb-stat-val">{current != null ? `$${current}` : '—'}</span>
        </div>
        <div className="atb-stat">
          <div className="atb-stat-pip atb-stat-pip--mean" />
          <span className="atb-stat-key">Mean Target</span>
          <span className="num atb-stat-val">{mean != null ? `$${mean.toFixed(2)}` : '—'}</span>
          {upside != null && (
            <span className={`num atb-stat-upside ${upside >= 0 ? 'text-positive' : 'text-negative'}`}>
              {upside >= 0 ? '+' : ''}{(upside * 100).toFixed(1)}%
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

const REC_MAP = {
  strong_buy: 'Strong Buy', buy: 'Buy', hold: 'Hold',
  sell: 'Sell', strong_sell: 'Strong Sell', underperform: 'Underperform',
}

function AnalystSection({ stock }) {
  return (
    <Card title="Analyst Consensus">
      <AnalystTargetBar stock={stock} />
      <div style={{ marginTop: 20 }}>
        <MetricRow label="Coverage"       value={stock.analyst_count != null ? `${stock.analyst_count} analysts` : '—'} />
        <MetricRow label="Recommendation" value={REC_MAP[stock.recommendation_key] ?? stock.recommendation_key ?? '—'} />
        <MetricRow label="High Target"    value={stock.target_high_price != null ? `$${stock.target_high_price.toFixed(2)}` : '—'} />
        <MetricRow label="Mean Target"    value={stock.target_mean_price != null ? `$${stock.target_mean_price.toFixed(2)}` : '—'} />
        <MetricRow label="Low Target"     value={stock.target_low_price  != null ? `$${stock.target_low_price.toFixed(2)}`  : '—'} />
      </div>
      <p className="card-note">Consensus reflects current analyst coverage; refreshed quarterly.</p>
    </Card>
  )
}


// ── Raw Data Section ───────────────────────────────────────────────────────────

const RAW_GROUPS = [
  {
    label: 'Income Statement',
    fields: [
      ['Revenue',              'revenue',              'cap'],
      ['Gross Profit',         'gross_profit',         'cap'],
      ['Operating Income',     'operating_income',     'cap'],
      ['Net Income',           'net_income',           'cap'],
      ['Free Cash Flow',       'free_cash_flow',       'cap'],
      ['R&D Expense',          'research_development', 'cap'],
      ['Capital Expenditures', 'capital_expenditures', 'cap'],
    ],
  },
  {
    label: 'Balance Sheet',
    fields: [
      ['Total Assets',          'total_assets',        'cap'],
      ['Total Debt',            'total_debt',           'cap'],
      ["Shareholders' Equity",  'shareholders_equity', 'cap'],
      ['Current Assets',        'current_assets',      'cap'],
      ['Current Liabilities',   'current_liabilities', 'cap'],
    ],
  },
  {
    label: 'Per Share',
    fields: [
      ['EPS (trailing)',     'eps',                'usd'],
      ['EPS (forward)',      'forward_eps',        'usd'],
      ['Shares Outstanding', 'shares_outstanding', 'cap'],
    ],
  },
  {
    label: 'Enterprise Value & Multiples',
    fields: [
      ['Enterprise Value', 'enterprise_value', 'cap'],
      ['EV / EBITDA',      'ev_ebitda',        'x1'],
      ['EV / Revenue',     'ev_revenue',       'x1'],
      ['Forward P/E',      'forward_pe',       'x1'],
    ],
  },
  {
    label: 'Dividends',
    fields: [
      ['Dividend Yield', 'dividend_yield', 'direct_pct'],
      ['Dividend Rate',  'dividend_rate',  'usd'],
      ['Payout Ratio',   'payout_ratio',   'pct'],
    ],
  },
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
      <div className="raw-groups">
        {RAW_GROUPS.map(group => (
          <div key={group.label} className="raw-group">
            <div className="raw-group-header">{group.label}</div>
            <table className="data-table data-table--raw">
              <tbody>
                {group.fields.map(([label, key, fmt]) => (
                  <tr key={key}>
                    <td className="raw-label">{label}</td>
                    <td className="raw-value num">{rawFmt(stock[key], fmt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
      <p className="card-note">
        Source: yfinance · Most recent annual filing.
        Capital Expenditures are negative (cash-outflow convention).
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
  const { ticker }                    = useParams()
  const [stock,       setStock]       = useState(null)
  const [sectorStats, setSectorStats] = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)

  const metrics = usePriceMetrics(ticker)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setStock(null)
    setSectorStats(null)

    getStock(ticker.toUpperCase())
      .then(data => {
        setStock(data)
        setLoading(false)

        if (data.sector) {
          getSectors()
            .then(sectors => {
              const s = sectors.find(sec => sec.sector === data.sector)
              setSectorStats(s ?? null)
            })
            .catch(() => {})
        }
      })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [ticker])

  if (loading) return <LoadingState ticker={ticker} />
  if (error)   return <ErrorState error={error} ticker={ticker} />
  if (!stock)  return null

  return (
    <div className="detail-page">

      <section id="overview" className="detail-section detail-section--first">
        <OverviewSection stock={stock} metrics={metrics} />
      </section>

      <section id="valuation" className="detail-section">
        <SectionTitle>Valuation</SectionTitle>
        <ValuationSection stock={stock} />
      </section>

      <section id="financials" className="detail-section">
        <SectionTitle>Fundamentals</SectionTitle>
        <FinancialsSection stock={stock} sectorStats={sectorStats} />
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
