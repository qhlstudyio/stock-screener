// src/hooks/useTickers.js
// Fetches the full ticker list from /api/tickers exactly once per page load.
//
// Module-level cache: if multiple components call useTickers() at the same
// time, only one network request is made and all hooks share the result.
// The cache lives for the lifetime of the JS module (cleared on page reload).

import { useState, useEffect } from 'react'
import { getTickers } from '../api/stocks.js'

let _cache   = null   // [TickerItem] once loaded, null before
let _promise = null   // in-flight request; deduplicated across hook instances

export function useTickers() {
  const [state, setState] = useState({
    tickers: _cache || [],
    loading: !_cache,
    error:   null,
  })

  useEffect(() => {
    // Already loaded — nothing to do
    if (_cache) return

    // Start the fetch if not already in-flight
    if (!_promise) {
      _promise = getTickers().then(data => {
        _cache = data
        return data
      })
    }

    let mounted = true
    _promise
      .then(data => {
        if (mounted) setState({ tickers: data, loading: false, error: null })
      })
      .catch(err => {
        // Reset promise so the next hook instance can retry
        _promise = null
        if (mounted) setState({ tickers: [], loading: false, error: err.message })
      })

    return () => { mounted = false }
  }, [])

  return state
}
