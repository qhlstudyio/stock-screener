// src/components/common/MetricTooltip.jsx
// Wraps any content with a hover-activated tooltip explaining a metric.
// Usage: <MetricTooltip text="Explanation text">Metric Name</MetricTooltip>

import { useState } from 'react'

export function MetricTooltip({ text, children }) {
  const [visible, setVisible] = useState(false)

  return (
    <span
      className="metric-tooltip-wrap"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      <span className="metric-tooltip-icon" aria-hidden="true">ⓘ</span>
      {visible && (
        <div className="metric-tooltip-box" role="tooltip">
          {text}
        </div>
      )}
    </span>
  )
}
