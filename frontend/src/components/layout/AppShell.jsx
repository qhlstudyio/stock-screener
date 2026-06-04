// src/components/layout/AppShell.jsx
// Root layout — rendered once, never unmounts during navigation.
//
// Structure:
//   .app-shell
//     Sidebar          (fixed left, 56px)
//     .app-content
//       .app-header    (sticky top, search bar)
//       .app-main      (scrollable page content)

import { useTheme }          from '../../hooks/useTheme.js'
import { useActiveSection }  from '../../hooks/useActiveSection.js'
import { NAV_ITEMS }         from '../../config/navigation.js'
import Sidebar               from './Sidebar.jsx'
import SearchBar             from './SearchBar.jsx'

// Section IDs derived from NAV_ITEMS once — stable reference, avoids re-renders
const SECTION_IDS = NAV_ITEMS
  .filter(item => item.sectionId !== null)
  .map(item => item.sectionId)

export default function AppShell({ children }) {
  const { theme, toggleTheme } = useTheme()
  const activeSection          = useActiveSection(SECTION_IDS)

  return (
    <div className="app-shell">
      <Sidebar
        theme={theme}
        onToggleTheme={toggleTheme}
        activeSection={activeSection}
      />

      <div className="app-content">
        <header className="app-header">
          <SearchBar />
        </header>

        <main className="app-main">
          {children}
        </main>
      </div>
    </div>
  )
}
