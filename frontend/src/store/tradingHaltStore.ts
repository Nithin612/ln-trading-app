import { create } from 'zustand'

/**
 * Client-side trading kill switch. When `halted`, the UI blocks NEW paper
 * orders and shows a banner. This is the user-facing halt; the live-order
 * kill-switch that stops the broker/live-worker is Phase-7 backend work.
 */
interface TradingHaltState {
  halted: boolean
  setHalted: (v: boolean) => void
  toggle: () => void
}

function readStored(): boolean {
  try {
    return localStorage.getItem('trading-halted') === 'true'
  } catch {
    return false
  }
}

function persist(v: boolean) {
  try { localStorage.setItem('trading-halted', String(v)) } catch { /* */ }
}

export const useTradingHaltStore = create<TradingHaltState>((set, get) => ({
  halted: readStored(),
  setHalted: (halted) => { persist(halted); set({ halted }) },
  toggle: () => { const next = !get().halted; persist(next); set({ halted: next }) },
}))
