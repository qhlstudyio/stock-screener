// src/components/common/Badge.jsx
// Coloured pill badge for valuation signals and sector labels.
//
// signal: 'undervalued' | 'fairly valued' | 'overvalued'
// type:   'sector' | 'warning' | 'info'   (fallback when signal is absent)

export default function Badge({ signal, label, type = 'sector' }) {
  // Map signal string to a CSS variant suffix
  const variant =
    signal === 'undervalued'   ? 'positive' :
    signal === 'overvalued'    ? 'negative' :
    signal === 'fairly valued' ? 'neutral'  :
    type

  return (
    <span className={`badge badge--${variant}`}>
      {label ?? signal}
    </span>
  )
}
