// src/App.jsx
// Application router. Wraps everything in AppShell so the sidebar
// and theme state persist across page navigations.

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell.jsx'
import ScreeningPage   from './pages/ScreeningPage.jsx'
import StockDetailPage from './pages/StockDetailPage.jsx'
import SpyPage         from './pages/SpyPage.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          {/* Default: redirect root to screening */}
          <Route path="/" element={<Navigate to="/screening" replace />} />

          {/* Main pages */}
          <Route path="/screening"     element={<ScreeningPage />} />
          <Route path="/stock/:ticker" element={<StockDetailPage />} />
          <Route path="/spy"           element={<SpyPage />} />

          {/* Fallback: anything unknown → screening */}
          <Route path="*" element={<Navigate to="/screening" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}
