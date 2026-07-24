import { create } from 'zustand'

export type Theme = 'slate' | 'midnight' | 'carbon' | 'ocean' | 'daybreak'

const THEMES: readonly Theme[] = ['slate', 'midnight', 'carbon', 'ocean', 'daybreak']

interface ThemeState {
  theme: Theme
  setTheme: (t: Theme) => void
  /** Toggle between the current dark theme and daybreak (light). */
  toggle: () => void
}

function readStored(): Theme {
  try {
    const v = localStorage.getItem('ui-theme')
    if (v && (THEMES as readonly string[]).includes(v)) return v as Theme
    // Backward compat: map old dark/light to new names
    if (v === 'dark') return 'slate'
    if (v === 'light') return 'daybreak'
  } catch { /* */ }
  return 'slate'
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: readStored(),
  setTheme: (theme) => {
    try { localStorage.setItem('ui-theme', theme) } catch { /* */ }
    set({ theme })
  },
  toggle: () => {
    const next: Theme = get().theme === 'daybreak' ? 'slate' : 'daybreak'
    try { localStorage.setItem('ui-theme', next) } catch { /* */ }
    set({ theme: next })
  },
}))
