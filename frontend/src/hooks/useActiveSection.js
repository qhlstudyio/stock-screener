// src/hooks/useActiveSection.js
// Tracks which section is currently visible in .app-main as the user scrolls.
//
// Key detail: body has overflow:hidden, so the viewport never scrolls.
// The actual scroll container is .app-main, which must be passed as `root`
// to IntersectionObserver — otherwise every section appears as intersecting
// (visible in the viewport) and the active state never changes.

import { useState, useEffect } from 'react'
import { useLocation }         from 'react-router-dom'

export function useActiveSection(sectionIds) {
  const [active, setActive] = useState(null)
  const { pathname }        = useLocation()

  useEffect(() => {
    setActive(null)   // reset on every route change
    if (!sectionIds || sectionIds.length === 0) return

    // body overflow:hidden → scroll happens inside .app-main, not the viewport
    const scrollRoot = document.querySelector('.app-main')
    if (!scrollRoot) return   // guard for SSR / test environments

    const visible = new Set()

    const callback = (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) visible.add(entry.target.id)
        else                      visible.delete(entry.target.id)
      })
      // Return the topmost visible section (first in display order)
      setActive(sectionIds.find(id => visible.has(id)) ?? null)
    }

    const observer = new IntersectionObserver(callback, {
      root:       scrollRoot,            // ← scroll container, not viewport
      rootMargin: '-60px 0px -40% 0px', // top offset accounts for sticky header
      threshold:  0.1,
    })

    sectionIds
      .map(id => document.getElementById(id))
      .filter(Boolean)
      .forEach(el => observer.observe(el))

    return () => observer.disconnect()
  }, [pathname])

  return active
}
