// src/main.jsx
// Application entry point.
// Imports global.css before mounting React so CSS variables are available
// from the very first render.

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/global.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)
