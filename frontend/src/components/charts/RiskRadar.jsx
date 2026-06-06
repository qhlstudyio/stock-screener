// src/components/charts/RiskRadar.jsx
// Radar chart with five risk dimensions normalised to 0-100.
// 100 always means the best possible risk characteristics.
// Hover tooltip explains each dimension and shows the raw value.

import { useTheme }               from '../../hooks/useTheme.js'
import { COLORS, getChartTheme } from '../../config/chartColors.js'
import { fmtDecimal, fmtPct }    from '../../utils/formatters.js'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

// Clamp v to [lo, hi], then map linearly to 0-100
function norm(v, lo, hi) {
  if (v == null) return 0
  return Math.round(((Math.min(Math.max(v, lo), hi) - lo) / (hi - lo)) * 100)
}

function buildRadarData(stock) {
  return [
    {
      metric: 'Sharpe',
      value:  norm(stock.sharpe, -1, 2.5),
      raw:    fmtDecimal(stock.sharpe, 2),
      tip:    'Sharpe Ratio — excess return per unit of risk. >1 is good, >2 is excellent.',
    },
    {
      metric: 'Alpha',
      value:  norm(stock.alpha, -0.20, 0.20),
      raw:    fmtPct(stock.alpha),
      tip:    'Jensen\'s Alpha (ann.) — excess return after market-beta is accounted for.',
    },
    {
      metric: 'Low Beta',
      value:  norm(2.0 - (stock.beta_yf ?? stock.beta ?? 1), 0, 2),
      raw:    fmtDecimal(stock.beta_yf ?? stock.beta, 2) + 'β',
      tip:    'Inverse of Beta — higher score means lower market sensitivity. Defensive stocks score well.',
    },
    {
      metric: 'Low Vol.',
      value:  norm(0.60 - (stock.volatility ?? 0.60), 0, 0.60),
      raw:    fmtPct(stock.volatility),
      tip:    'Inverse of annualised volatility — higher score means more stable price history.',
    },
    {
      metric: 'Drawdown',
      value:  norm(-0.80 - (stock.max_drawdown ?? -0.80), -0.80, 0),
      raw:    fmtPct(stock.max_drawdown),
      tip:    'Inverse of max peak-to-trough loss — higher score means smaller historical drawdown.',
    },
  ]
}

function RadarTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-date">{d.metric}</div>
      <div className="chart-tooltip-row">
        <span className="chart-tooltip-label">Score</span>
        <span className="chart-tooltip-val num">{d.value}/100</span>
      </div>
      <div className="chart-tooltip-row">
        <span className="chart-tooltip-label">Value</span>
        <span className="chart-tooltip-val num">{d.raw}</span>
      </div>
      <p style={{ fontSize: 10, color: 'var(--text2)', marginTop: 6, maxWidth: 180, lineHeight: 1.5 }}>
        {d.tip}
      </p>
    </div>
  )
}

export default function RiskRadar({ stock }) {
  const { theme } = useTheme()
  const ct        = getChartTheme(theme === 'dark')
  const data      = buildRadarData(stock)

  return (
    <div>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data} margin={{ top: 10, right: 28, left: 28, bottom: 10 }}>
          <PolarGrid stroke={ct.grid} />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fill: ct.tick, fontSize: 10 }}
          />
          <PolarRadiusAxis
            angle={90} domain={[0, 100]}
            tick={false} axisLine={false}
          />
          <Tooltip content={<RadarTooltip />} />
          <Radar
            name="Risk"
            dataKey="value"
            stroke={COLORS.sky}
            fill={COLORS.sky}
            fillOpacity={0.18}
            strokeWidth={2}
            dot={{ r: 3, fill: COLORS.sky }}
          />
        </RadarChart>
      </ResponsiveContainer>
      <p className="card-note">
        All axes normalised 0–100 where 100 = best risk characteristics.
        Hover each point for the raw value and explanation.
      </p>
    </div>
  )
}
