// src/config/navigation.js
// Single source of truth for sidebar navigation items.
//
// To add a new section (e.g. Growth):
//   1. Import an icon from lucide-react
//   2. Add one entry to NAV_ITEMS with the new sectionId
//   3. Create the corresponding <section id="growth"> in StockDetailPage
//   The sidebar renders, routes, and highlights automatically.
//
// Field reference:
//   id         — stable key, used as React key and for active-state tracking
//   label      — shown in the hover tooltip
//   icon       — Lucide icon component
//   route      — if set, clicking navigates to this path (e.g. /screening)
//   sectionId  — if set, clicking scrolls to <section id={sectionId}> on the
//                stock detail page; null for navigation-only items

import {
  LayoutGrid,
  LayoutDashboard,
  DollarSign,
  BarChart2,
  Shield,
  Users,
  Table2,
} from 'lucide-react'

export const NAV_ITEMS = [
  {
    id:        'screening',
    label:     'Screening',
    icon:      LayoutGrid,
    route:     '/screening',
    sectionId: null,
  },
  {
    id:        'overview',
    label:     'Overview',
    icon:      LayoutDashboard,
    route:     null,
    sectionId: 'overview',
  },
  {
    id:        'valuation',
    label:     'Valuation',
    icon:      DollarSign,
    route:     null,
    sectionId: 'valuation',
  },
  {
    id:        'financials',
    label:     'Financials',
    icon:      BarChart2,
    route:     null,
    sectionId: 'financials',
  },
  {
    id:        'risk',
    label:     'Risk',
    icon:      Shield,
    route:     null,
    sectionId: 'risk',
  },
  {
    id:        'analyst',
    label:     'Analyst',
    icon:      Users,
    route:     null,
    sectionId: 'analyst',
  },
  {
    id:        'raw-data',
    label:     'Raw Data',
    icon:      Table2,
    route:     null,
    sectionId: 'raw-data',
  },
]
