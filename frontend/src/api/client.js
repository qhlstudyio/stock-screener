// src/api/client.js
// Base fetch wrapper for all API calls.
//
// All requests go to /api/... which Vite proxies to http://localhost:8000
// during development. In production, nginx handles the same routing.
//
// On non-2xx responses, a structured Error is thrown with:
//   err.message  — FastAPI's detail string, or a generic HTTP status message
//   err.status   — HTTP status code (number)
//
// Usage: import { apiFetch } from './client.js'
//        const data = await apiFetch('/stock/AAPL')

const BASE = '/api'

export async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch {
      // JSON parse failed — stick with the generic message
    }
    const err = new Error(detail)
    err.status = res.status
    throw err
  }

  return res.json()
}
