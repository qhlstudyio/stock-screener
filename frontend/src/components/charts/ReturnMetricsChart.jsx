// src/components/charts/ReturnMetricsChart.jsx
// Grouped bar chart: ROE / ROA / ROIC for the stock vs sector median.
// sectorStats is optional — if absent, shows single bars for the stock only.

import { useTheme }               from '../../hooks/useTheme.js'
import { COLORS, getChartTheme } from '../../config/chartColors.js'
import { fmtPct }                from '../../utils/formatters.js'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'

const METRICS = [
  {
    key: 'roe',  label: 'ROE',
    tip: 'Return on Equity: net income ÷ shareholders\' equity. Shows how efficiently a company uses investor capital.',
  },
  {
    key: 'roa',  label: 'ROA',
    tip: 'Return on Assets: net income ÷ total assets. Not distorted by leverage — more comparable across companies.',
  },
  {
    key: 'roic', label: 'ROIC',
    tip: 'Return on Invested Capital: net income ÷ (debt + equity). The most comprehensive capital-efficiency measure.',
  },
]

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-date">{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} className="chart-tooltip-row">
          <span className="chart-tooltip-label" style={{ color: p.fill }}>{p.name}</span>
          <span className="chart-tooltip-val num">
            {p.value != null ? fmtPct(p.value) : '—'}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function ReturnMetricsChart({ stock, sectorStats }) {
  const { theme }  = useTheme()
  const ct         = getChartTheme(theme === 'dark')
  const hasSector  = sectorStats != null

  const data = METRICS.map(m => ({
    name:   m.label,
    Stock:  stock[m.key] ?? null,
    Sector: sectorStats ? sectorStats[`avg_${m.key}`] ?? null : null,
  }))

  const fmtY = v => fmtPct(v, 0)

  return (
    <div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} barGap={4} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: ct.tick, fontSize: 11 }}
            axisLine={false} tickLine={false}
          />
          <YAxis
            tick={{ fill: ct.tick, fontSize: 10 }}
            axisLine={false} tickLine={false}
            tickFormatter={fmtY}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(56,189,248,0.05)' }} />
          {hasSector && (
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
              formatter={name => (
                <span style={{ color: name === 'Stock' ? COLORS.sky : COLORS.violet }}>
                  {name === 'Stock' ? stock.ticker : stock.sector ?? 'Sector'}
                </span>
              )}
            />
          )}
          <Bar dataKey="Stock" fill={COLORS.sky + 'cc'} radius={[4,4,0,0]} name="Stock" />
          {hasSector && (
            <Bar dataKey="Sector" fill={COLORS.violet + 'cc'} radius={[4,4,0,0]} name="Sector" />
          )}
        </BarChart>
      </ResponsiveContainer>
      <p className="card-note">
        {hasSector
          ? `${stock.ticker} vs ${stock.sector} sector median.`
          : 'Sector median unavailable.'}{' '}
        High ROE driven by buybacks may be misleading — check edge-case alerts.
      </p>
    </div>
  )
}
