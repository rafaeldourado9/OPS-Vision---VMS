import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'
import { errorHandler } from './services/errorHandler'

// Initialize global error handler
errorHandler.initialize()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <Toaster
      position="top-right"
      toastOptions={{
        style: {
          background: 'var(--surface)',
          color: 'var(--text-1)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          fontSize: '14px',
        },
        success: { iconTheme: { primary: 'var(--success)', secondary: 'var(--surface)' } },
        error:   { iconTheme: { primary: 'var(--danger)',  secondary: 'var(--surface)' } },
      }}
    />
  </StrictMode>,
)
