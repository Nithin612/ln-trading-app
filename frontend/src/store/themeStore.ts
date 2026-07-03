import { create } from 'zustand'

export type Theme = 'midnight' | 'carbon' | 'ocean' | 'daybreak'

interface ThemeState {
  theme: Theme
  setTheme: (t: Theme) => void
  /** Toggle between the current dark theme and daybreak (light). */
  toggle: () => void
}

function readStored(): Theme {
  try {
    const v = localStorage.getItem('ui-theme')
    if (v === 'midnight' || v === 'carbon' || v === 'ocean' || v === 'daybreak') return v
    // Backward compat: map old dark/light to new names
    if (v === 'dark') return 'midnight'
    if (v === 'light') return 'daybreak'
  } catch { /* */ }
  return 'midnight'
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: readStored(),
  setTheme: (theme) => {
    try { localStorage.setItem('ui-theme', theme) } catch { /* */ }
    set({ theme })
  },
  toggle: () => {
    const next: Theme = get().theme === 'daybreak' ? 'midnight' : 'daybreak'
    try { localStorage.setItem('ui-theme', next) } catch { /* */ }
    set({ theme: next })
  },
}))
