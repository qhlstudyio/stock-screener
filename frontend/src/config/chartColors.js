// src/config/chartColors.js
// Shared chart color palette — used by all chart components.
// Colors chosen to be visible on both dark (#0A0C12) and light (#EEF2F7) backgrounds.
// Sky = current stock / primary series.  Violet = SPY benchmark / comparison.

export const COLORS = {
  sky:     '#38BDF8',   // stock lines, primary metric
  violet:  '#A78BFA',   // SPY benchmark, comparison series
  emerald: '#34D399',   // gross profit, positive / good
  amber:   '#FBB74B',   // net income, warning / neutral
  rose:    '#F87171',   // negative / caution / overvalued
  teal:    '#2DD4BF',   // FCF, sixth series
}

// Score-breakdown segment colours — keys match screener.score_breakdown dict
export const SCORE_COLORS = {
  gross_margin:  COLORS.sky,
  profit_margin: COLORS.violet,
  roe:           COLORS.emerald,
  debt_ratio:    COLORS.amber,
  pe_valuation:  COLORS.rose,
  dcf_valuation: COLORS.teal,
}

// Chart grid / tick colours — hardcoded because recharts cannot resolve CSS vars
export function getChartTheme(isDark) {
  return isDark
    ? { grid: '#1C2138', tick: '#4E5A70', zero: '#2D3555' }
    : { grid: '#D8E0EC', tick: '#94A3B8', zero: '#CBD5E1' }
}
