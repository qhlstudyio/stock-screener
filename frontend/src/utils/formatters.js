// src/utils/formatters.js
// Pure formatting functions for financial data display.
// Every function accepts null / undefined and returns '—' for missing values.

// ── Percentage (decimal input: 0.253 → "25.3%") ───────────────────────────────
export function fmtPct(v, decimals = 1) {
  if (v == null) return '—'
  return (v * 100).toFixed(decimals) + '%'
}

// ── Multiplier (28.53 → "28.5x") ─────────────────────────────────────────────
export function fmtX(v, decimals = 1) {
  if (v == null) return '—'
  return v.toFixed(decimals) + 'x'
}

// ── Large USD amount — handles negative values (e.g. CapEx from yfinance) ─────
// yfinance returns capital_expenditures as a negative number (cash outflow).
// Without this fix, negatives skip all magnitude checks and fall through to
// toLocaleString(), producing "$-12,715,000,000" instead of "-$12.7B".
export function fmtCap(v) {
  if (v == null) return '—'
  const abs  = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e12) return sign + '$' + (abs / 1e12).toFixed(2) + 'T'
  if (abs >= 1e9)  return sign + '$' + (abs / 1e9).toFixed(1)  + 'B'
  if (abs >= 1e6)  return sign + '$' + (abs / 1e6).toFixed(0)  + 'M'
  return sign + '$' + abs.toLocaleString()
}

// ── Composite score (72.4) ────────────────────────────────────────────────────
export function fmtScore(v) {
  if (v == null) return '—'
  return v.toFixed(1)
}

// ── Generic decimal (for ratios like D/E, current ratio) ─────────────────────
export function fmtDecimal(v, decimals = 2) {
  if (v == null) return '—'
  return v.toFixed(decimals)
}
