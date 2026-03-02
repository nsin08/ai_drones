import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './theme.css'
import './index.css'
import './App.css'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import V4Routes from './v4/routes.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <V4Routes />
    </ErrorBoundary>
  </StrictMode>,
)
