// src/components/common/PriceChart.jsx
// Recharts line chart showing normalised price return (%) from period start.
//
// X-axis design (industry standard):
//   - 1M / 3M : weekly ticks, labelled "Jun 4"
//   - 6M+ :     monthly ticks (first trading day of each month), labelled "Jun '25"
//   - Max ~6 evenly-spaced ticks regardless of data length
//   - No auto-skip or tickCount — ticks are explicitly calculated to prevent
//     duplicate month names (the "Jun Jun Jul Jul" problem)
//
// Color convention (matches all other chart components):
//   Stock line → Sky  #38BDF8
//   SPY line   → Violet #A78BFA  (dashed)

import { useState, useEffect, useMemo } from 'react'
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend,
} from 'recharts'
import { getPrices }  from '../../api/stocks.js'
import { useTheme }   from '../../hooks/useTheme.js'

const PERIODS = ['1m', '3m', '6m', '1y', '2y', '5y']

// Sky = stock (primary), Violet = SPY benchmark. Matches all other chart components.
const CHART_COLORS = {
  dark:  { stock: '#38BDF8', spy: '#A78BFA', grid: '#1C2138', zero: '#2D3555' },
  light: { stock: '#0284C7', spy: '#7C5CDB', grid: '#D8E0EC', zero: '#C8D4E8' },
}


// ── X-axis tick calculation ────────────────────────────────────────────────────
// Industry standard: show the first trading day of each month (or week for
// short periods), then downsample to at most 6 evenly-spaced labels.

function calcXTicks(chartData, period) {
  if (!chartData.length) return []

  const dates = chartData.map(d => d.date)
  const seen  = new Set()
  const candidates = []

  const useWeekly = period === '1m' || period === '3m'

  dates.forEach(date => {
    let key
    if (useWeekly) {
      // First trading day of each calendar week
      const ms = new Date(date + 'T00:00:00').getTime()
      key = Math.floor(ms / (7 * 24 * 3600 * 1000))
    } else {
      // First trading day of each calendar month
      key = date.slice(0, 7)           // "YYYY-MM"
    }
    if (!seen.has(key)) { seen.add(key); candidates.push(date) }
  })

  // Keep at most 6 labels, evenly spaced
  if (candidates.length <= 6) return candidates
  const step = Math.ceil(candidates.length / 6)
  return candidates.filter((_, i) => i % step === 0)
}

function formatDateTick(dateStr, period) {
  const d   = new Date(dateStr + 'T00:00:00')
  const mon = d.toLocaleString('en', { month: 'short' })
  const yr  = `'${String(d.getFullYear()).slice(2)}`
  // Short periods: show "Jun 4" — long periods: show "Jun '25"
  return (period === '1m' || period === '3m')
    ? `${mon} ${d.getDate()}`
    : `${mon} ${yr}`
}


// ── Helpers ────────────────────────────────────────────────────────────────────

function normalise(data) {
  if (!data?.length) return []
  const base = data[0].close
  if (!base) return []
  return data.map(d => ({
    date:   d.date,
    return: parseFloat(((d.close / base - 1) * 100).toFixed(3)),
  }))
}


// ── Custom tooltip ─────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label, ticker, showSpy }) {
  if (!active || !payload?.length) return null
  const stockPt = payload.find(p => p.dataKey === 'stock')
  const spyPt   = payload.find(p => p.dataKey === 'spy')
  const fmt     = v => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-date">{label}</div>
      {stockPt && (
        <div className="chart-tooltip-row">
          <span className="chart-tooltip-label">{ticker}</span>
          <span className={`chart-tooltip-val num ${stockPt.value >= 0 ? 'text-positive' : 'text-negative'}`}>
            {fmt(stockPt.value)}
          </span>
        </div>
      )}
      {showSpy && spyPt && (
        <div className="chart-tooltip-row">
          <span className="chart-tooltip-label">SPY</span>
          <span className="chart-tooltip-val num">{fmt(spyPt.value)}</span>
        </div>
      )}
    </div>
  )
}


// ── Component ──────────────────────────────────────────────────────────────────

export default function PriceChart({ ticker, showSpy = true, defaultPeriod = '1y' }) {
  const { theme }               = useTheme()
  const colors                  = CHART_COLORS[theme] ?? CHART_COLORS.dark

  const [period, setPeriod]     = useState(defaultPeriod)
  const [stockRaw, setStockRaw] = useState([])
  const [spyRaw,   setSpyRaw]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)

    const fetches = [getPrices(ticker, period)]
    if (showSpy) fetches.push(getPrices('SPY', period))

    Promise.all(fetches)
      .then(([tData, sData = []]) => {
        setStockRaw(tData)
        setSpyRaw(sData)
        setLoading(false)
      })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [ticker, period, showSpy])

  // Merge normalised stock and SPY data on date
  const chartData = useMemo(() => {
    const stockNorm = normalise(stockRaw)
    const spyNorm   = normalise(spyRaw)
    const spyMap    = new Map(spyNorm.map(d => [d.date, d.return]))
    return stockNorm.map(d => ({
      date:  d.date,
      stock: d.return,
      spy:   spyMap.get(d.date) ?? null,
    }))
  }, [stockRaw, spyRaw])

  // Explicit X-axis ticks — prevents duplicate month labels
  const xTicks = useMemo(() => calcXTicks(chartData, period), [chartData, period])

  // Y-axis range with padding
  const yValues = chartData.flatMap(d => [d.stock, d.spy].filter(v => v != null && isFinite(v)))
  const yMin = yValues.length ? Math.floor(Math.min(...yValues) * 1.15) : -20
  const yMax = yValues.length ? Math.ceil(Math.max(...yValues)  * 1.15) :  20
  const domain = [isFinite(yMin) ? yMin : -20, isFinite(yMax) ? yMax : 20]

  const tickFmt = v => `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`

  return (
    <div className="price-chart">
      {/* Period selector */}
      <div className="period-row">
        {PERIODS.map(p => (
          <button
            key={p}
            className={`period-btn${period === p ? ' active' : ''}`}
            onClick={() => setPeriod(p)}
          >
            {p.toUpperCase()}
          </button>
        ))}
      </div>

      {loading && (
        <div className="chart-loading">
          <div className="spinner" />
          <span>Loading prices…</span>
        </div>
      )}

      {error && !loading && (
        <div className="chart-error">Price data unavailable: {error}</div>
      )}

      {!loading && !error && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />

            <XAxis
              dataKey="date"
              tick={{ fill: colors.spy, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              ticks={xTicks}
              tickFormatter={d => formatDateTick(d, period)}
            />

            <YAxis
              tick={{ fill: colors.spy, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={tickFmt}
              domain={domain}
              width={52}
            />

            <Tooltip
              content={<ChartTooltip ticker={ticker} showSpy={showSpy} />}
              cursor={{ stroke: colors.spy, strokeWidth: 1 }}
            />

            <ReferenceLine y={0} stroke={colors.zero} strokeWidth={1} />

            <Line
              type="monotone"
              dataKey="stock"
              stroke={colors.stock}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: colors.stock }}
              name={ticker}
            />

            {showSpy && (
              <Line
                type="monotone"
                dataKey="spy"
                stroke={colors.spy}
                strokeWidth={1.5}
                strokeDasharray="5 4"
                dot={false}
                activeDot={{ r: 3, fill: colors.spy }}
                name="SPY"
                connectNulls
              />
            )}

            {showSpy && (
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8, color: colors.spy }}
                formatter={value => (
                  <span style={{ color: value === ticker ? colors.stock : colors.spy }}>
                    {value}
                  </span>
                )}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
