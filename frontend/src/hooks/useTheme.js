// src/hooks/useTheme.js
// Manages dark / light theme state.
//
// - Persists preference to localStorage so it survives page refreshes.
// - Applies the theme by setting data-theme on <html> so all CSS variables
//   update instantly without a re-render of every component.
// - The inline script in index.html reads the same localStorage key and sets
//   data-theme synchronously before React mounts, preventing any flash of
//   wrong theme on first load.

import { useState, useEffect } from 'react'

const STORAGE_KEY = 'stock-screener-theme'
const DEFAULT     = 'dark'

export function useTheme() {
  const [theme, setTheme] = useState(() => {
    // Read from localStorage on first render.
    // Falls back to DEFAULT if nothing is stored.
    return localStorage.getItem(STORAGE_KEY) || DEFAULT
  })

  useEffect(() => {
    // Keep the DOM attribute and localStorage in sync whenever theme changes.
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))

  return { theme, toggleTheme }
}
