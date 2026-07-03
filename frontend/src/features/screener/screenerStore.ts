import { create } from 'zustand'
import type { FilterSpec, ScreenerRequest, ScreenerResult, SavedScreen } from '@/lib/api/stocks'

interface ScreenerState {
  filters: FilterSpec[]
  logic: 'AND' | 'OR'
  sortBy: string
  sortDir: 'asc' | 'desc'
  limit: number
  offset: number
  result: ScreenerResult | null
  isRunning: boolean
  activeSavedScreen: SavedScreen | null

  addFilter: () => void
  updateFilter: (index: number, patch: Partial<FilterSpec>) => void
  removeFilter: (index: number) => void
  setLogic: (logic: 'AND' | 'OR') => void
  setSort: (by: string, dir: 'asc' | 'desc') => void
  setResult: (result: ScreenerResult | null) => void
  setRunning: (running: boolean) => void
  loadSavedScreen: (screen: SavedScreen) => void
  resetFilters: () => void
  toRequest: () => ScreenerRequest
}

const BLANK_FILTER: FilterSpec = { field: 'is_nifty50', op: 'eq', value: true }

export const useScreenerStore = create<ScreenerState>((set, get) => ({
  filters: [],
  logic: 'AND',
  sortBy: 'symbol',
  sortDir: 'asc',
  limit: 50,
  offset: 0,
  result: null,
  isRunning: false,
  activeSavedScreen: null,

  addFilter: () =>
    set(s => ({ filters: [...s.filters, { ...BLANK_FILTER }] })),

  updateFilter: (index, patch) =>
    set(s => {
      const filters = [...s.filters]
      filters[index] = { ...filters[index], ...patch }
      return { filters }
    }),

  removeFilter: (index) =>
    set(s => ({ filters: s.filters.filter((_, i) => i !== index) })),

  setLogic: (logic) => set({ logic }),

  setSort: (sortBy, sortDir) => set({ sortBy, sortDir }),

  setResult: (result) => set({ result }),

  setRunning: (isRunning) => set({ isRunning }),

  loadSavedScreen: (screen) => {
    const spec = screen.filter_spec
    set({
      filters: spec.filters ?? [],
      logic: spec.logic ?? 'AND',
      sortBy: spec.sort_by ?? 'symbol',
      sortDir: spec.sort_dir ?? 'asc',
      limit: spec.limit ?? 50,
      offset: 0,
      activeSavedScreen: screen,
      result: null,
    })
  },

  resetFilters: () =>
    set({
      filters: [],
      logic: 'AND',
      sortBy: 'symbol',
      sortDir: 'asc',
      result: null,
      activeSavedScreen: null,
    }),

  toRequest: () => {
    const { filters, logic, sortBy, sortDir, limit, offset } = get()
    return { filters, logic, sort_by: sortBy, sort_dir: sortDir, limit, offset }
  },
}))
