// src/components/charts/ProfitWaterfall.jsx
// Horizontal bar chart showing how revenue cascades down to FCF.
// Each bar width = that layer's margin % of revenue.
// Colors encode each level; hover tooltips explain what each metric means.

import { COLORS } from '../../config/chartColors.js'
import { MetricTooltip } from '../common/MetricTooltip.jsx'
import { fmtPct, fmtCap } from '../../utils/formatters.js'

const LEVELS = [
  {
    pctKey: null,
    absKey: 'revenue',
    label:  'Revenue',
    color:  COLORS.sky,
    tip:    'Total sales — the starting point. All margins below are a percentage of this.',
  },
  {
    pctKey: 'gross_margin',
    absKey: 'gross_profit',
    label:  'Gross profit',
    color:  COLORS.emerald,
    tip:    'Revenue minus direct production costs. Measures pricing power and unit economics before any overhead.',
  },
  {
    pctKey: 'operating_margin',
    absKey: 'operating_income',
    label:  'Operating income',
    color:  COLORS.violet,
    tip:    'After deducting R&D, sales, and admin expenses. The most honest measure of core business efficiency.',
  },
  {
    pctKey: 'profit_margin',
    absKey: 'net_income',
    label:  'Net income',
    color:  COLORS.amber,
    tip:    'After interest and taxes. Affected by capital structure, so less comparable across companies.',
  },
  {
    pctKey: 'fcf_margin',
    absKey: 'free_cash_flow',
    label:  'Free cash flow',
    color:  COLORS.teal,
    tip:    'Net income minus capital expenditure. Actual cash the business generates. Harder to manipulate than accounting profit.',
  },
]

export default function ProfitWaterfall({ stock }) {
  return (
    <div className="waterfall">
      {LEVELS.map(({ pctKey, absKey, label, color, tip }) => {
        const pct    = pctKey ? stock[pctKey] : 1.0   // revenue = 100%
        const absVal = stock[absKey]
        const barPct = pct != null ? Math.max(0, Math.min(pct * 100, 100)) : 0

        return (
          <div key={label} className="waterfall-row">
            <div className="waterfall-label">
              <MetricTooltip text={tip}>{label}</MetricTooltip>
            </div>
            <div className="waterfall-track">
              <div
                className="waterfall-bar"
                style={{ width: `${barPct}%`, background: color }}
              />
            </div>
            <div className="waterfall-pct num" style={{ color }}>
              {pct != null ? (pct * 100).toFixed(1) + '%' : '—'}
            </div>
            <div className="waterfall-abs num">
              {fmtCap(absVal)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
