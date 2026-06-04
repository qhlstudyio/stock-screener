// src/pages/SpyPage.jsx
// Dedicated page for SPY (SPDR S&P 500 ETF Trust).
// SPY is the benchmark used for Alpha, Beta, and vs-SPY calculations
// throughout the screener. This page shows its price history and key stats.
//
// Financial ratios (PE, margins, etc.) are not shown — they are not meaningful
// for an index ETF. Only metrics derived from price history are displayed.

import { useState, useEffect } from 'react'
import { getStock }            from '../api/stocks.js'
import { fmtPct, fmtCap, fmtDecimal } from '../utils/formatters.js'
import Card      from '../components/common/Card.jsx'
import MetricRow from '../components/common/MetricRow.jsx'
import PriceChart from '../components/common/PriceChart.jsx'

// ── Helpers ────────────────────────────────────────────────────────────────────

const p = fmtPct

function signCls(v) {
  if (v == null) return ''
  return v > 0 ? 'text-positive' : 'text-negative'
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function BenchmarkBanner() {
  return (
    <div className="spy-banner">
      <div className="spy-banner-title">
        <span className="spy-ticker num">SPY</span>
        <span className="spy-name">SPDR S&amp;P 500 ETF Trust</span>
      </div>
      <p className="spy-description">
        SPY tracks the S&P 500 index and is used as the market benchmark in this
        screener. All <strong>Alpha</strong>, <strong>Beta</strong>, and{' '}
        <strong>vs-SPY returns</strong> for individual stocks are calculated
        relative to SPY. Data is end-of-day (EOD).
      </p>
    </div>
  )
}

function ReturnsCard({ stock }) {
  const periods = [
    { label: '1 Month',  key: 'return_1m' },
    { label: '3 Months', key: 'return_3m' },
    { label: '6 Months', key: 'return_6m' },
    { label: '1 Year',   key: 'return_1y' },
  ]
  return (
    <Card title="Price Returns">
      {periods.map(({ label, key }) => (
        <MetricRow
          key={key}
          label={label}
          value={<span className={signCls(stock[key])}>{p(stock[key])}</span>}
        />
      ))}
      <p className="card-note">
        Returns normalised to the start of each period. End-of-day prices.
      </p>
    </Card>
  )
}

function RiskCard({ stock }) {
  return (
    <Card title="Risk Statistics">
      <MetricRow label="Volatility (ann.)" value={p(stock.volatility)} />
      <MetricRow label="Sharpe Ratio"      value={fmtDecimal(stock.sharpe, 2)} />
      <MetricRow label="Max Drawdown"      value={p(stock.max_drawdown)} />
      <p className="card-note">
        Volatility and drawdown are calculated from the full available price history.
      </p>
    </Card>
  )
}

function InfoCard({ stock }) {
  // Not all info fields are populated for an ETF — render only what is available
  const rows = [
    ['Market Cap / AUM',   fmtCap(stock.market_cap)],
    ['Dividend Yield',     stock.dividend_yield != null ? stock.dividend_yield.toFixed(2) + '%' : '—'],
    ['Dividend Rate',      stock.dividend_rate  != null ? `$${stock.dividend_rate.toFixed(2)}`  : '—'],
  ].filter(([, v]) => v !== '—')

  if (rows.length === 0) return null

  return (
    <Card title="Fund Information">
      {rows.map(([label, val]) => (
        <MetricRow key={label} label={label} value={val} />
      ))}
    </Card>
  )
}

// ── Loading / Error ────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="detail-loading">
      <div className="spinner" />
      <span>Loading SPY…</span>
    </div>
  )
}

function ErrorState({ error }) {
  return (
    <div className="detail-error" style={{ padding: '48px 32px' }}>
      <h2>Could not load SPY data</h2>
      <p>{error}</p>
      <p className="card-note" style={{ marginTop: 8 }}>
        SPY price data requires bootstrap.py to have completed successfully.
      </p>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function SpyPage() {
  const [stock, setStock]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getStock('SPY')
      .then(data => { setStock(data); setLoading(false) })
      .catch(err  => { setError(err.message); setLoading(false) })
  }, [])

  if (loading) return <LoadingState />
  if (error)   return <ErrorState error={error} />
  if (!stock)  return null

  return (
    <div className="detail-page">

      {/* Banner */}
      <div className="detail-section detail-section--first">
        <BenchmarkBanner />
      </div>

      {/* Price chart — SPY only, 5-year default */}
      <div className="detail-section">
        <Card title="SPY Price History — Total Return (%)">
          <PriceChart ticker="SPY" showSpy={false} defaultPeriod="5y" />
        </Card>
      </div>

      {/* Returns + Risk side-by-side */}
      <div className="detail-section">
        <div className="card-grid-2">
          <ReturnsCard stock={stock} />
          <RiskCard stock={stock} />
        </div>
        <InfoCard stock={stock} />
      </div>

    </div>
  )
}
