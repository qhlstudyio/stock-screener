// src/components/layout/Sidebar.jsx
// Fixed left sidebar with icon navigation and theme toggle.
//
// Active state logic:
//   - "Screening" icon is active when the current route is /screening or /spy.
//   - Section icons (Overview, Valuation, …) are active based on which section
//     is currently scrolled into view — handled by useActiveSection (added M2).
//     In M1, they are always inactive (greyed out) unless explicitly passed.
//
// The divider line separates the page-navigation icon (Screening) from the
// section-scroll icons (Overview → Raw Data).

import { Fragment } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Sun, Moon } from 'lucide-react'
import { NAV_ITEMS } from '../../config/navigation.js'

export default function Sidebar({ theme, onToggleTheme, activeSection = null }) {
  const navigate      = useNavigate()
  const { pathname }  = useLocation()

  const isScreeningRoute = pathname === '/screening' || pathname === '/spy'

  const handleClick = (item) => {
    if (item.route) {
      navigate(item.route)
      return
    }
    if (item.sectionId) {
      const el = document.getElementById(item.sectionId)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const isActive = (item) => {
    if (item.id === 'screening') return isScreeningRoute
    // Section active state comes from useActiveSection (wired up in M2)
    return activeSection === item.sectionId
  }

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item, i) => {
          const Icon         = item.icon
          const showDivider  = i === 1   // single divider between Screening and Overview
          return (
            <Fragment key={item.id}>
              {showDivider && <div className="sidebar-divider" />}
              <button
                className={`sidebar-btn${isActive(item) ? ' active' : ''}`}
                data-label={item.label}
                onClick={() => handleClick(item)}
                aria-label={item.label}
              >
                <Icon size={18} strokeWidth={1.75} />
              </button>
            </Fragment>
          )
        })}
      </nav>

      {/* Theme toggle — always at the bottom */}
      <button
        className="sidebar-btn"
        data-label={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        onClick={onToggleTheme}
        aria-label="Toggle theme"
      >
        {theme === 'dark'
          ? <Sun  size={18} strokeWidth={1.75} />
          : <Moon size={18} strokeWidth={1.75} />
        }
      </button>
    </aside>
  )
}
