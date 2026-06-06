// src/hooks/usePriceMetrics.js
// Derives daily price change and 52-week range from the /prices endpoint.
// The same endpoint powers PriceChart — this hook reads the last two data
// points for daily delta, and min/max over the full 1y window for the range.

import { useState, useEffect } from 'react'
import { getPrices } from '../api/stocks.js'

export function usePriceMetrics(ticker) {
  const [metrics, setMetrics] = useState(null)

  useEffect(() => {
    if (!ticker) return
    setMetrics(null)

    getPrices(ticker, '1y')
      .then(data => {
        if (!data || data.length < 2) return
        const last = data[data.length - 1]
        const prev = data[data.length - 2]
        const dailyChange    = last.close - prev.close
        const dailyChangePct = dailyChange / prev.close
        const closes         = data.map(d => d.close)
        setMetrics({
          dailyChange,
          dailyChangePct,
          week52High: Math.max(...closes),
          week52Low:  Math.min(...closes),
        })
      })
      .catch(() => {}) // non-critical; header renders fine without it
  }, [ticker])

  return metrics
}
