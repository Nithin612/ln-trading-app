import { api } from './client'

export interface WatchlistItem {
  stock_id: number
  symbol: string
  company_name: string
  added_at: string
}

export interface Watchlist {
  id: number
  name: string
  created_at: string
  updated_at: string
  items: WatchlistItem[]
}

export const watchlistsApi = {
  list: (token: string) => api.get<Watchlist[]>('/watchlists', token),

  create: (name: string, token: string) =>
    api.post<Watchlist>('/watchlists', { name }, token),

  rename: (id: number, name: string, token: string) =>
    api.patch<Watchlist>(`/watchlists/${id}`, { name }, token),

  remove: (id: number, token: string) => api.delete<void>(`/watchlists/${id}`, token),

  addStock: (id: number, stockId: number, token: string) =>
    api.post<Watchlist>(`/watchlists/${id}/stocks`, { stock_id: stockId }, token),

  removeStock: (id: number, stockId: number, token: string) =>
    api.delete<Watchlist>(`/watchlists/${id}/stocks/${stockId}`, token),
}
