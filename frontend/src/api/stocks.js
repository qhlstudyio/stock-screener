// src/api/stocks.js
// All API call functions. Never call fetch() directly in a component.

import { apiFetch } from './client.js'

export const getTickers    = ()              => apiFetch('/tickers')
export const getStock      = (ticker)        => apiFetch(`/stock/${ticker}`)
export const getSectors    = ()              => apiFetch('/sectors')
export const getHealth     = ()              => apiFetch('/health')

export const getMembership = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return apiFetch(`/sp500/membership${qs ? `?${qs}` : ''}`)
}

export const getStocks = (params = {}) => {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  )
  const qs = new URLSearchParams(clean).toString()
  return apiFetch(`/stocks${qs ? `?${qs}` : ''}`)
}

// Historical close prices for a ticker.
// period: '1m' | '3m' | '6m' | '1y' | '2y' | '5y'
// Returns: [{ date, close, volume }] ordered by date ascending.
export const getPrices = (ticker, period = '1y') =>
  apiFetch(`/prices/${ticker}?period=${period}`)
