// src/components/layout/SearchBar.jsx
// Global search with client-side autocomplete.
//
// Behaviour:
//   - Ticker list is fetched once by useTickers() and filtered in memory.
//   - Results are ranked: exact ticker > ticker prefix > name prefix > contains.
//   - Keyboard: ArrowUp / ArrowDown to move, Enter to select, Esc to close.
//   - Keyboard shortcut: press '/' anywhere to focus the search box.
//   - SPY navigates to /spy; all other tickers navigate to /stock/:ticker.
//   - Click outside the box to close the dropdown.

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search }      from 'lucide-react'
import { useTickers }  from '../../hooks/useTickers.js'

const MAX_RESULTS = 8

// ── Search ranking ─────────────────────────────────────────────────────────────
function filterAndRank(tickers, query) {
  if (!query.trim()) return []

  const q = query.trim().toUpperCase()

  return tickers
    .map(item => {
      const t = item.ticker.toUpperCase()
      const n = (item.company_name || '').toUpperCase()

      let score = 0
      if (t === q)                       score = 4   // exact ticker match
      else if (t.startsWith(q))          score = 3   // ticker prefix
      else if (n.startsWith(q))          score = 2   // company name prefix
      else if (t.includes(q) || n.includes(q)) score = 1  // contains

      return { ...item, _score: score }
    })
    .filter(item => item._score > 0)
    .sort((a, b) => b._score - a._score || a.ticker.localeCompare(b.ticker))
    .slice(0, MAX_RESULTS)
}

// ── Component ──────────────────────────────────────────────────────────────────
export default function SearchBar() {
  const navigate             = useNavigate()
  const { tickers, loading } = useTickers()

  const [query,   setQuery]   = useState('')
  const [results, setResults] = useState([])
  const [open,    setOpen]    = useState(false)
  const [cursor,  setCursor]  = useState(-1)   // keyboard-highlighted index (-1 = none)

  const inputRef    = useRef(null)
  const dropdownRef = useRef(null)

  // Recompute results on every query change
  useEffect(() => {
    setResults(filterAndRank(tickers, query))
    setCursor(-1)
  }, [query, tickers])

  // Close dropdown when clicking outside both the input and the dropdown
  useEffect(() => {
    const handler = (e) => {
      const insideInput    = inputRef.current?.contains(e.target)
      const insideDropdown = dropdownRef.current?.contains(e.target)
      if (!insideInput && !insideDropdown) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Global '/' shortcut — focus the search box
  useEffect(() => {
    const handler = (e) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const handleSelect = useCallback((item) => {
    setQuery('')
    setOpen(false)
    setCursor(-1)
    navigate(item.is_benchmark ? '/spy' : `/stock/${item.ticker}`)
  }, [navigate])

  const handleKeyDown = (e) => {
    if (!open || results.length === 0) {
      if (e.key === 'Escape') setOpen(false)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setCursor(c => Math.min(c + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor(c => Math.max(c - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (cursor >= 0 && results[cursor]) handleSelect(results[cursor])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const hasResults  = results.length > 0
  const showEmpty   = open && query.trim() && !hasResults && !loading
  const showDropdown = open && (hasResults || showEmpty)

  return (
    <div className="search-wrap">

      {/* Input */}
      <div className="search-input-wrap">
        <Search className="search-icon" size={15} strokeWidth={2} />
        <input
          ref={inputRef}
          className="search-input"
          type="text"
          value={query}
          placeholder="Search S&P 500 — 503 companies  ·  Press / to focus"
          autoComplete="off"
          spellCheck={false}
          onChange={e => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <ul
          className="search-dropdown"
          ref={dropdownRef}
          role="listbox"
        >
          {results.map((item, i) => (
            <li
              key={item.ticker}
              className={`search-item${i === cursor ? ' search-item--focused' : ''}`}
              role="option"
              aria-selected={i === cursor}
              // onMouseDown instead of onClick: fires before input blur,
              // so the dropdown stays open long enough to register the click
              onMouseDown={() => handleSelect(item)}
              onMouseEnter={() => setCursor(i)}
            >
              <span className="search-item-ticker num">{item.ticker}</span>
              <span className="search-item-name">{item.company_name}</span>
              {item.is_benchmark
                ? <span className="search-item-badge search-item-badge--benchmark">Benchmark</span>
                : item.sector && <span className="search-item-badge">{item.sector}</span>
              }
            </li>
          ))}

          {showEmpty && (
            <li className="search-empty">
              No results — only S&amp;P 500 companies are covered
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
