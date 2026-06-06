// src/components/charts/ValuationRuler.jsx
// SVG "ruler" showing where the current price sits relative to intrinsic
// value estimates. Markers alternate above / below the track to minimise
// label collision when estimates are close together.

import { COLORS } from '../../config/chartColors.js'

export default function ValuationRuler({ stock }) {
  const {
    graham_number,
    current_price,
    dcf_scenarios,
  } = stock

  const bear  = dcf_scenarios?.bear?.intrinsic_value
  const base  = dcf_scenarios?.base?.intrinsic_value
  const bull  = dcf_scenarios?.bull?.intrinsic_value
  const price = current_price

  // Need at least one estimate + current price to be useful
  const estimates = [graham_number, bear, base, bull].filter(v => v != null && v > 0)
  if (!price || estimates.length === 0) {
    return (
      <p className="card-note" style={{ marginTop: 8 }}>
        Valuation estimates unavailable — may require positive FCF and EPS.
      </p>
    )
  }

  // Range with generous padding so the ruler never feels cramped
  const allVals  = [...estimates, price]
  const minVal   = Math.min(...allVals) * 0.80
  const maxVal   = Math.max(...allVals) * 1.20
  const range    = maxVal - minVal || 1

  // Map value to 0-100% of the SVG track width (track from x=12 to x=288 = 276px)
  const TRACK_X = 12
  const TRACK_W = 276
  const TRACK_Y = 52
  const toX = v => TRACK_X + ((v - minVal) / range) * TRACK_W

  const markers = [
    graham_number && {
      val: graham_number, label: 'Graham',   color: COLORS.amber,   above: true,
    },
    bear && {
      val: bear,          label: 'Bear DCF', color: COLORS.rose,    above: false,
    },
    base && {
      val: base,          label: 'Base DCF', color: COLORS.violet,  above: true,
    },
    bull && {
      val: bull,          label: 'Bull DCF', color: COLORS.emerald, above: false,
    },
  ].filter(Boolean)

  const priceX = toX(price)

  return (
    <div className="valuation-ruler">
      <svg
        width="100%"
        viewBox="0 0 300 100"
        style={{ overflow: 'visible', display: 'block' }}
        aria-label="Valuation ruler showing price vs intrinsic value estimates"
      >
        {/* Background track */}
        <rect x={TRACK_X} y={TRACK_Y} width={TRACK_W} height={8} rx={4} fill="var(--border)" />

        {/* DCF range band */}
        {bear != null && bull != null && (
          <rect
            x={toX(Math.min(bear, bull))}
            y={TRACK_Y}
            width={Math.abs(toX(bull) - toX(bear))}
            height={8}
            fill={COLORS.violet}
            opacity={0.18}
          />
        )}

        {/* Value markers (alternating above / below) */}
        {markers.map(m => {
          const x    = toX(m.val)
          const yTop = m.above ? TRACK_Y - 20 : TRACK_Y + 22
          return (
            <g key={m.label}>
              <line
                x1={x} y1={TRACK_Y - 2}
                x2={x} y2={TRACK_Y + 10}
                stroke={m.color} strokeWidth={1.5}
              />
              <text
                x={x} y={yTop}
                fill={m.color} fontSize={8}
                textAnchor="middle"
                fontFamily="system-ui, sans-serif"
              >
                {m.label}
              </text>
              <text
                x={x} y={yTop + 10}
                fill={m.color} fontSize={8}
                textAnchor="middle"
                fontFamily="monospace"
              >
                ${m.val.toFixed(0)}
              </text>
            </g>
          )
        })}

        {/* Current price pill */}
        <line
          x1={priceX} y1={TRACK_Y - 8}
          x2={priceX} y2={TRACK_Y + 16}
          stroke={COLORS.sky} strokeWidth={2.5}
        />
        <rect
          x={priceX - 24} y={TRACK_Y - 24}
          width={48} height={16}
          rx={8} fill={COLORS.sky}
        />
        <text
          x={priceX} y={TRACK_Y - 13}
          fill="#06101a" fontSize={9} fontWeight="700"
          textAnchor="middle"
          fontFamily="monospace"
        >
          ${price}
        </text>
      </svg>

      {/* Legend */}
      <div className="ruler-legend">
        {markers.map(m => (
          <div key={m.label} className="ruler-legend-item">
            <div className="ruler-legend-dot" style={{ background: m.color }} />
            <span>{m.label}</span>
            <span className="num" style={{ color: m.color }}>
              ${m.val.toFixed(0)}
            </span>
          </div>
        ))}
        <div className="ruler-legend-item">
          <div className="ruler-legend-dot" style={{ background: COLORS.sky }} />
          <span>Current</span>
          <span className="num" style={{ color: COLORS.sky }}>${price}</span>
        </div>
      </div>
    </div>
  )
}
