import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// The non-null assertion (!) tells TypeScript "trust me, this element
// exists" — getElementById's return type is `HTMLElement | null` since
// TypeScript can't know at compile time whether index.html actually has
// a <div id="root">. It does (Vite's template creates it), so this is safe.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
