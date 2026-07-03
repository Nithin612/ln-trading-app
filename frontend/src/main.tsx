import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import '@/styles/globals.css'
import { AuthProvider } from '@/components/auth/AuthProvider'
import { ToastProvider } from '@/components/ui/toast'
import { router } from '@/router'

/* Apply persisted theme + font prefs to <html> synchronously before first paint
   to avoid a flash of the wrong theme. The ThemeApplicator in AppShell keeps
   them in sync reactively; this just seeds the initial values. */
;(function applyBootPrefs() {
  try {
    const el = document.documentElement

    // Theme — map old dark/light to new names for backward compat
    let theme = localStorage.getItem('ui-theme') ?? 'midnight'
    if (theme === 'dark') theme = 'midnight'
    if (theme === 'light') theme = 'daybreak'
    el.setAttribute('data-theme', theme)

    // Legacy discrete font size
    const fontSize = localStorage.getItem('ui-font-size') ?? 'md'
    el.setAttribute('data-font-size', fontSize)

    // Legacy font family
    const fontFamily = localStorage.getItem('ui-font-family') ?? 'inter'
    el.setAttribute('data-font-family', fontFamily)

    // Continuous font size (slider) — takes precedence over discrete
    const fontSizePx = localStorage.getItem('ui-font-size-px')
    if (fontSizePx) el.style.setProperty('--ui-font-size', `${fontSizePx}px`)

    // Split fonts
    const uiFont = localStorage.getItem('ui-font')
    if (uiFont) el.setAttribute('data-ui-font', uiFont)
    const numFont = localStorage.getItem('ui-num-font')
    if (numFont) el.setAttribute('data-num-font', numFont)
  } catch { /* localStorage may be unavailable */ }
})()

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
