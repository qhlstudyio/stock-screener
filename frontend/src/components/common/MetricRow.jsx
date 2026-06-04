// src/components/common/MetricRow.jsx
// One row inside a data card: label  [progress bar]  value
//
// bar    — raw numeric value used to compute bar fill width; omit to hide bar
// barMax — what constitutes a "full" bar (default 1.0)
// The bar is capped at 100% fill regardless of raw value.

export default function MetricRow({ label, value, bar, barMax = 1 }) {
  const hasBar  = bar != null && barMax > 0
  const fillPct = hasBar ? Math.min(Math.max(bar / barMax, 0), 1) * 100 : 0

  return (
    <div className="metric-row">
      <span className="metric-label">{label}</span>
      {hasBar && (
        <div className="metric-bar-wrap">
          <div className="metric-bar-fill" style={{ width: `${fillPct}%` }} />
        </div>
      )}
      <span className="metric-value num">{value ?? '—'}</span>
    </div>
  )
}
