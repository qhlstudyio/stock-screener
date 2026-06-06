// src/components/charts/ReturnBars.jsx
// Grouped bar chart: stock return vs SPY return for 1M / 3M / 6M / 1Y.
// Both series normalized to percentage (decimal input × 100 for display).

import { useTheme }               from '../../hooks/useTheme.js'
import { COLORS, getChartTheme } from '../../config/chartColors.js'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'

const PERIODS = [
  { label: '1M', stockKey: 'return_1m', spyKey: 'vs_spy_1m' },
  { label: '3M', stockKey: 'return_3m', spyKey: 'vs_spy_3m' },
  { label: '6M', stockKey: 'return_6m', spyKey: 'vs_spy_6m' },
  { label: '1Y', stockKey: 'return_1y', spyKey: 'vs_spy_1y' },
]

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const fmt = v => v != null ? `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%` : '—'
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-date">{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} className="chart-tooltip-row">
          <span className="chart-tooltip-label" style={{ color: p.fill }}>
            {p.name}
          </span>
          <span
            className={`chart-tooltip-val num ${
              p.value >= 0 ? 'text-positive' : 'text-negative'
            }`}
          >
            {fmt(p.value)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function ReturnBars({ stock }) {
  const { theme } = useTheme()
  const ct        = getChartTheme(theme === 'dark')
  const ticker    = stock.ticker

  const data = PERIODS.map(p => {
    const stockRet  = stock[p.stockKey]
    const excess    = stock[p.spyKey]
    const spyRet    = stockRet != null && excess != null ? stockRet - excess : null
    return { period: p.label, [ticker]: stockRet, SPY: spyRet }
  })

  const fmtY = v => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(0)}%`

  return (
    <div>
      <ResponsiveContainer width="100%" height={210}>
        <BarChart data={data} barGap={4} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} vertical={false} />
          <XAxis
            dataKey="period"
            tick={{ fill: ct.tick, fontSize: 11 }}
            axisLine={false} tickLine={false}
          />
          <YAxis
            tick={{ fill: ct.tick, fontSize: 10 }}
            axisLine={false} tickLine={false}
            tickFormatter={fmtY}
          />
          <ReferenceLine y={0} stroke={ct.grid} strokeWidth={1.5} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(56,189,248,0.04)' }} />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
            formatter={name => (
              <span style={{ color: name === ticker ? COLORS.sky : COLORS.violet }}>
                {name}
              </span>
            )}
          />
          <Bar dataKey={ticker} fill={COLORS.sky + 'cc'} radius={[4,4,0,0]} />
          <Bar dataKey="SPY"    fill={COLORS.violet + 'cc'} radius={[4,4,0,0]} />
        </BarChart>
      </ResponsiveContainer>
      <p className="card-note">
        Returns indexed from period start. SPY reconstructed from stock return minus vs-SPY excess.
      </p>
    </div>
  )
}
