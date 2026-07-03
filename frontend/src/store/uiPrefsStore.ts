import { create } from 'zustand'

export type FontFamily = 'geist' | 'inter' | 'system'
export type FontSize   = 'sm' | 'md' | 'lg'
export type UiFont     = 'inter' | 'geist' | 'ibm-plex-sans' | 'roboto' | 'system'
export type NumFont    = 'jetbrains-mono' | 'ibm-plex-mono' | 'roboto-mono' | 'inter'

interface UiPrefsState {
  /* Legacy discrete fields — kept for AppShell ThemeApplicator backward compat */
  fontSize:   FontSize
  fontFamily: FontFamily

  /* New continuous font size (12–22 px) */
  fontSizePx: number

  /* Split font selection */
  uiFont:  UiFont
  numFont: NumFont

  setFontSize:   (s: FontSize)   => void
  setFontFamily: (f: FontFamily) => void
  setFontSizePx: (px: number)    => void
  setUiFont:     (f: UiFont)     => void
  setNumFont:    (f: NumFont)    => void
}

function read<T extends string>(key: string, allowed: T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    if (v && allowed.includes(v as T)) return v as T
  } catch { /* */ }
  return fallback
}

function readNum(key: string, min: number, max: number, fallback: number): number {
  try {
    const v = parseFloat(localStorage.getItem(key) ?? '')
    if (!isNaN(v) && v >= min && v <= max) return v
  } catch { /* */ }
  return fallback
}

function persist(key: string, value: string) {
  try { localStorage.setItem(key, value) } catch { /* */ }
}

export const useUiPrefsStore = create<UiPrefsState>((set) => ({
  fontSize:   read<FontSize>('ui-font-size',   ['sm', 'md', 'lg'],             'md'),
  fontFamily: read<FontFamily>('ui-font-family', ['geist', 'inter', 'system'], 'inter'),
  fontSizePx: readNum('ui-font-size-px', 12, 22, 15),
  uiFont:     read<UiFont>('ui-font',  ['inter', 'geist', 'ibm-plex-sans', 'roboto', 'system'], 'inter'),
  numFont:    read<NumFont>('ui-num-font', ['jetbrains-mono', 'ibm-plex-mono', 'roboto-mono', 'inter'], 'jetbrains-mono'),

  setFontSize: (fontSize) => {
    persist('ui-font-size', fontSize)
    set({ fontSize })
  },
  setFontFamily: (fontFamily) => {
    persist('ui-font-family', fontFamily)
    set({ fontFamily })
  },
  setFontSizePx: (fontSizePx) => {
    persist('ui-font-size-px', String(fontSizePx))
    document.documentElement.style.setProperty('--ui-font-size', `${fontSizePx}px`)
    set({ fontSizePx })
  },
  setUiFont: (uiFont) => {
    persist('ui-font', uiFont)
    document.documentElement.setAttribute('data-ui-font', uiFont)
    set({ uiFont })
  },
  setNumFont: (numFont) => {
    persist('ui-num-font', numFont)
    document.documentElement.setAttribute('data-num-font', numFont)
    set({ numFont })
  },
}))
