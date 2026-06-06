// src/components/charts/ScoreDonut.jsx
// Doughnut chart showing composite score breakdown.
// Center overlay (absolute div) shows total score — recharts PieChart
// doesn't support native center text so we layer a div on top.

import { PieChart, Pie, Cell, Tooltip } from 'recharts'
import { COLORS, SCORE_COLORS }        from '../../config/chartColors.js'
import { fmtScore }                    from '../../utils/formatters.js'

const SEGMENTS = [
  { key: 'gross_margin',  label: 'Gross margin',  max: 15 },
  { key: 'profit_margin', label: 'Profit margin', max: 15 },
  { key: 'roe',           label: 'ROE',           max: 20 },
  { key: 'debt_ratio',    label: 'Debt ratio',    max: 15 },
  { key: 'pe_valuation',  label: 'P/E valuation', max: 15 },
  { key: 'dcf_valuation', label: 'DCF valuation', max: 20 },
]

export default function ScoreDonut({ score, scoreBreakdown }) {
  if (!scoreBreakdown) return null

  const total     = score ?? 0
  const remaining = Math.max(0, 100 - total)

  const pieData = [
    ...SEGMENTS.map(s => ({
      name:  s.label,
      value: scoreBreakdown[s.key] ?? 0,
      color: SCORE_COLORS[s.key],
      max:   s.max,
    })),
    { name: '__gap__', value: remaining, color: null },
  ]

  return (
    <div className="score-donut">
      <div className="score-donut-inner">

        {/* Chart + center overlay */}
        <div style={{ position: 'relative', width: 150, height: 150, flexShrink: 0 }}>
          <PieChart width={150} height={150}>
            <Pie
              data={pieData}
              cx={75} cy={75}
              innerRadius={48} outerRadius={68}
              startAngle={90} endAngle={-270}
              dataKey="value"
              strokeWidth={0}
            >
              {pieData.map((d, i) => (
                <Cell
                  key={i}
                  fill={d.color ? d.color + 'e0' : 'var(--border)'}
                />
              ))}
            </Pie>
            <Tooltip
              wrapperStyle={{ zIndex: 10 }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const d = payload[0].payload
                if (d.name === '__gap__') return null
                return (
                  <div className="chart-tooltip">
                    <div className="chart-tooltip-date">{d.name}</div>
                    <div className="chart-tooltip-row">
                      <span className="num" style={{ color: d.color }}>
                        {d.value.toFixed(1)} / {d.max} pts
                      </span>
                    </div>
                  </div>
                )
              }}
            />
          </PieChart>

          {/* Center text overlay */}
          <div className="score-donut-center-overlay">
            <div className="score-donut-number num">{fmtScore(total)}</div>
            <div className="score-donut-label">/ 100</div>
          </div>
        </div>

        {/* Breakdown legend */}
        <div className="score-donut-legend">
          {SEGMENTS.map(s => (
            <div key={s.key} className="score-legend-row">
              <div className="score-legend-dot" style={{ background: SCORE_COLORS[s.key] }} />
              <span className="score-legend-name">{s.label}</span>
              <span className="score-legend-val num">
                {(scoreBreakdown[s.key] ?? 0).toFixed(1)}/{s.max}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
