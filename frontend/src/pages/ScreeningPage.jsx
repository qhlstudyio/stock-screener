// src/pages/ScreeningPage.jsx
// S&P 500 sector screening — sortable table with optional heatmap view.
//
// Data flow:
//   1. Mount → fetch sector list (/api/sectors) for the dropdown + tiles.
//   2. Sector select → fetch all stocks in that sector (/api/stocks?sector=…).
//   3. Filter / sort is applied client-side on the already-fetched data,
//      so there is no extra network call per filter change.
//
// Column config (COLS) drives both the table headers and heatmap coloring.
// Adding a new column: add one entry to COLS, no other changes needed.

import { useState, useEffect, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSectors, getStocks } from '../api/stocks.js'
import { fmtPct, fmtX, fmtCap, fmtScore } from '../utils/formatters.js'


// ── Column definitions ─────────────────────────────────────────────────────────
//
// hm:  include in heatmap coloring
// dir: 'asc'  → higher is better (green)
//      'desc' → lower is better (green)
// lo / hi: absolute thresholds
//   asc:  value < lo = red,  lo–hi = mild,  > hi = green
//   desc: value > hi = red,  lo–hi = mild,  < lo = green

const COLS = [
  { key: 'ticker',           label: 'Company',     fmt: 'company', hm: false },
  { key: 'score',            label: 'Score',       fmt: 'score',   hm: true,  dir: 'asc',  lo: 40,   hi: 65   },
  { key: 'market_cap',       label: 'Mkt Cap',     fmt: 'cap',     hm: false },
  { key: 'pe_ratio',         label: 'P/E',         fmt: 'x1',      hm: true,  dir: 'desc', lo: 15,   hi: 35   },
  { key: 'gross_margin',     label: 'Gross Mgn',   fmt: 'pct',     hm: true,  dir: 'asc',  lo: 0.20, hi: 0.50 },
  { key: 'operating_margin', label: 'Op. Margin',  fmt: 'pct',     hm: true,  dir: 'asc',  lo: 0.10, hi: 0.25 },
  { key: 'profit_margin',    label: 'Net Margin',  fmt: 'pct',     hm: true,  dir: 'asc',  lo: 0.05, hi: 0.20 },
  { key: 'roe',              label: 'ROE',         fmt: 'pct',     hm: true,  dir: 'asc',  lo: 0.10, hi: 0.25 },
  { key: 'debt_ratio',       label: 'Debt/Assets', fmt: 'pct',     hm: true,  dir: 'desc', lo: 0.30, hi: 0.65 },
]


// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtCell(col, stock) {
  const v = stock[col.key]
  if (v == null) return '—'
  switch (col.fmt) {
    case 'score': return fmtScore(v)
    case 'cap':   return fmtCap(v)
    case 'x1':    return fmtX(v)
    case 'pct':   return fmtPct(v)
    default:      return String(v)
  }
}

// Background colour for heatmap cells.
// Uses absolute thresholds so colours are consistent regardless of which stocks
// are currently visible (no relative/normalised colouring within the view).
function heatBg(col, value) {
  if (!col.hm || value == null) return undefined
  if (col.dir === 'asc') {
    if (value >= col.hi) return 'rgba(16,185,129,0.18)'   // green
    if (value >= col.lo) return 'rgba(16,185,129,0.09)'   // mild green
    return 'rgba(244,63,94,0.16)'                         // red
  } else {
    if (value <= col.lo) return 'rgba(16,185,129,0.18)'
    if (value <= col.hi) return 'rgba(16,185,129,0.09)'
    return 'rgba(244,63,94,0.16)'
  }
}

function sortFn(a, b, key, asc) {
  const va = a[key], vb = b[key]
  if (va == null && vb == null) return 0
  if (va == null) return 1   // nulls always last
  if (vb == null) return -1
  const d = va < vb ? -1 : va > vb ? 1 : 0
  return asc ? d : -d
}

// Filter values: Score and P/E are direct numbers;
// ROE and Debt are entered as percentages by the user (10 → 0.10 internally).
function passesFilters(s, { minScore, maxPe, minRoe, maxDebt }) {
  if (minScore != null && (s.score      ?? 0) < minScore)       return false
  if (maxPe    != null && s.pe_ratio   != null && s.pe_ratio > maxPe) return false
  if (minRoe   != null && (s.roe        ?? 0) < minRoe / 100)   return false
  if (maxDebt  != null && (s.debt_ratio ?? 1) > maxDebt / 100)  return false
  return true
}

const FILTERS_EMPTY = { minScore: null, maxPe: null, minRoe: null, maxDebt: null }


// ── Sub-components ─────────────────────────────────────────────────────────────

// Sector tiles — shown when no sector is selected
function SectorGrid({ sectors, onSelect }) {
  return (
    <div className="sector-grid">
      {sectors.map(s => (
        <button key={s.sector} className="sector-tile" onClick={() => onSelect(s.sector)}>
          <div className="sector-tile-name">{s.sector}</div>
          <div className="sector-tile-count num">{s.ticker_count} stocks</div>
          <div className="sector-tile-stats">
            {s.avg_pe_ratio     && <span className="num">PE {s.avg_pe_ratio.toFixed(0)}x</span>}
            {s.avg_gross_margin && <span className="num">GM {(s.avg_gross_margin * 100).toFixed(0)}%</span>}
          </div>
        </button>
      ))}
    </div>
  )
}

// Filter bar — number inputs for quick screening
function FilterRow({ filters, onChange }) {
  const set = (key, raw) => {
    const v = raw === '' ? null : Number(raw)
    onChange({ ...filters, [key]: isNaN(v) ? null : v })
  }

  const fields = [
    { key: 'minScore', label: 'Score ≥',  suffix: '',  placeholder: '0–100' },
    { key: 'maxPe',    label: 'P/E ≤',    suffix: 'x', placeholder: 'e.g. 30' },
    { key: 'minRoe',   label: 'ROE ≥',    suffix: '%', placeholder: 'e.g. 10' },
    { key: 'maxDebt',  label: 'Debt ≤',   suffix: '%', placeholder: 'e.g. 60' },
  ]

  const hasFilters = Object.values(filters).some(v => v != null)

  return (
    <div className="filter-row">
      <span className="filter-label">Filter</span>
      {fields.map(({ key, label, suffix, placeholder }) => (
        <label key={key} className="filter-item">
          <span className="filter-item-label">{label}</span>
          <div className="filter-item-input-wrap">
            <input
              className="filter-input num"
              type="number"
              placeholder={placeholder}
              value={filters[key] ?? ''}
              onChange={e => set(key, e.target.value)}
            />
            {suffix && <span className="filter-suffix">{suffix}</span>}
          </div>
        </label>
      ))}
      {hasFilters && (
        <button className="filter-clear" onClick={() => onChange(FILTERS_EMPTY)}>
          Clear
        </button>
      )}
    </div>
  )
}

// Sort direction icon
function SortIcon({ colKey, sortBy, ascending }) {
  if (colKey !== sortBy) return <span className="sort-icon sort-icon--idle">↕</span>
  return <span className="sort-icon">{ascending ? '▲' : '▼'}</span>
}

// Main data table (doubles as heatmap when heatmap=true)
function StockTable({ stocks, sortBy, ascending, onSort, onRowClick, heatmap }) {
  if (stocks.length === 0) {
    return <p className="screening-empty">No stocks match your filters.</p>
  }

  return (
    <div className="stock-table-wrap">
      <table className="stock-table">
        <thead>
          <tr>
            {COLS.map(col => (
              <th
                key={col.key}
                className={`stock-th${col.key === 'ticker' ? ' stock-th--company' : ''}`}
                onClick={() => onSort(col.key)}
              >
                <span className="stock-th-label">{col.label}</span>
                <SortIcon colKey={col.key} sortBy={sortBy} ascending={ascending} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {stocks.map(s => (
            <tr key={s.ticker} className="stock-row" onClick={() => onRowClick(s.ticker)}>
              {COLS.map(col => (
                <td
                  key={col.key}
                  className={`stock-td${col.key === 'ticker' ? ' stock-td--company' : ' num'}`}
                  style={heatmap ? { backgroundColor: heatBg(col, s[col.key]) } : undefined}
                >
                  {col.key === 'ticker' ? (
                    <span className="company-cell">
                      <span className="company-ticker num">{s.ticker}</span>
                      <span className="company-name">{s.company_name}</span>
                    </span>
                  ) : (
                    fmtCell(col, s)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


// ── Page ───────────────────────────────────────────────────────────────────────

export default function ScreeningPage() {
  const navigate = useNavigate()

  const [sectors,   setSectors]   = useState([])
  const [sector,    setSector]    = useState(null)
  const [stocks,    setStocks]    = useState([])
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [sortBy,    setSortBy]    = useState('score')
  const [ascending, setAscending] = useState(false)
  const [heatmap,   setHeatmap]   = useState(false)
  const [filters,   setFilters]   = useState(FILTERS_EMPTY)

  // Sector list — fetched once on mount
  useEffect(() => {
    getSectors()
      .then(setSectors)
      .catch(err => console.error('[Screening] sector load:', err))
  }, [])

  // Stock list — fetched whenever the sector changes
  useEffect(() => {
    if (!sector) { setStocks([]); return }
    setLoading(true)
    setError(null)
    setFilters(FILTERS_EMPTY)  // reset filters on sector switch

    getStocks({ sector })
      .then(data => { setStocks(data); setLoading(false) })
      .catch(err  => { setError(err.message); setLoading(false) })
  }, [sector])

  // Filtered + sorted view (pure client-side, no network)
  const displayed = useMemo(
    () => stocks.filter(s => passesFilters(s, filters)).sort((a, b) => sortFn(a, b, sortBy, ascending)),
    [stocks, filters, sortBy, ascending]
  )

  const handleSort = useCallback((key) => {
    if (sortBy === key) setAscending(a => !a)
    else { setSortBy(key); setAscending(false) }
  }, [sortBy])

  // ── Render ─────────────────────────────────────────────────────────────────

  const subtitle = sector
    ? `${sector}  ·  ${displayed.length} of ${stocks.length} stocks`
    : 'Select a sector to begin'

  return (
    <div className="screening-page">

      {/* Header row */}
      <div className="screening-header">
        <div>
          <h1 className="screening-title">Screening</h1>
          <p className="screening-subtitle">{subtitle}</p>
        </div>

        {sector && (
          <div className="view-toggle">
            <button
              className={`view-toggle-btn${!heatmap ? ' active' : ''}`}
              onClick={() => setHeatmap(false)}
            >Table</button>
            <button
              className={`view-toggle-btn${heatmap ? ' active' : ''}`}
              onClick={() => setHeatmap(true)}
            >Heatmap</button>
          </div>
        )}
      </div>

      {/* Sector selector */}
      <div className="sector-bar">
        <select
          className="sector-select"
          value={sector ?? ''}
          onChange={e => setSector(e.target.value || null)}
        >
          <option value="">All sectors…</option>
          {sectors.map(s => (
            <option key={s.sector} value={s.sector}>{s.sector}</option>
          ))}
        </select>
        {sector && (
          <button className="sector-clear-btn" onClick={() => setSector(null)}>
            ✕ Clear
          </button>
        )}
      </div>

      {/* Filters (once stocks are loaded) */}
      {sector && !loading && stocks.length > 0 && (
        <FilterRow filters={filters} onChange={setFilters} />
      )}

      {/* Sector tiles — initial state when no sector selected */}
      {!sector && !loading && sectors.length > 0 && (
        <SectorGrid sectors={sectors} onSelect={setSector} />
      )}

      {/* Loading state */}
      {loading && (
        <div className="screening-loading">
          <div className="spinner" />
          <span>Loading {sector}…</span>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="screening-error">
          Failed to load stocks: {error}
        </div>
      )}

      {/* Table / Heatmap */}
      {!loading && !error && sector && (
        <StockTable
          stocks={displayed}
          sortBy={sortBy}
          ascending={ascending}
          onSort={handleSort}
          onRowClick={t => navigate(`/stock/${t}`)}
          heatmap={heatmap}
        />
      )}

    </div>
  )
}
