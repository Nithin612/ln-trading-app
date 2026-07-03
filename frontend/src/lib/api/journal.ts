import { api } from './client'

export type EmotionBefore = 'fear' | 'neutral' | 'confident' | 'greed' | 'anxious'
export type EmotionAfter = 'regret' | 'satisfied' | 'neutral' | 'excited' | 'frustrated'

export interface JournalEntry {
  id: string
  user_id: number
  position_id: string | null
  stock_id: number | null
  symbol: string | null
  trade_date: string
  side: 'LONG' | 'SHORT' | null
  entry_price: string | null
  exit_price: string | null
  quantity: number | null
  realized_pnl: string | null
  notes: string | null
  lesson: string | null
  emotion_before: EmotionBefore | null
  emotion_after: EmotionAfter | null
  screenshot_paths: string[]
  tags: string[]
  entry_type: 'auto' | 'manual'
  created_at: string
  updated_at: string
}

export interface JournalListResponse {
  total: number
  entries: JournalEntry[]
}

export interface JournalEntryCreate {
  stock_id?: number | null
  position_id?: string | null
  trade_date: string
  side?: 'LONG' | 'SHORT' | null
  entry_price?: string | null
  exit_price?: string | null
  quantity?: number | null
  realized_pnl?: string | null
  notes?: string | null
  lesson?: string | null
  emotion_before?: EmotionBefore | null
  emotion_after?: EmotionAfter | null
  tags?: string[]
}

export interface JournalEntryUpdate {
  trade_date?: string
  side?: 'LONG' | 'SHORT' | null
  entry_price?: string | null
  exit_price?: string | null
  quantity?: number | null
  realized_pnl?: string | null
  notes?: string | null
  lesson?: string | null
  emotion_before?: EmotionBefore | null
  emotion_after?: EmotionAfter | null
  tags?: string[]
}

export interface JournalListParams {
  q?: string
  stock_id?: number
  start_date?: string
  end_date?: string
  emotion_before?: EmotionBefore
  emotion_after?: EmotionAfter
  entry_type?: 'auto' | 'manual'
  limit?: number
  offset?: number
}

export interface EmotionCount {
  emotion: string
  count: number
  avg_pnl: string | null
}

export interface EmotionAnalytics {
  before: EmotionCount[]
  after: EmotionCount[]
  total_entries: number
}

export const EMOTIONS_BEFORE: EmotionBefore[] = ['fear', 'neutral', 'confident', 'greed', 'anxious']
export const EMOTIONS_AFTER: EmotionAfter[] = ['regret', 'satisfied', 'neutral', 'excited', 'frustrated']

export const journalApi = {
  list(params: JournalListParams = {}): Promise<JournalListResponse> {
    const q = new URLSearchParams()
    if (params.q) q.set('q', params.q)
    if (params.stock_id != null) q.set('stock_id', String(params.stock_id))
    if (params.start_date) q.set('start_date', params.start_date)
    if (params.end_date) q.set('end_date', params.end_date)
    if (params.emotion_before) q.set('emotion_before', params.emotion_before)
    if (params.emotion_after) q.set('emotion_after', params.emotion_after)
    if (params.entry_type) q.set('entry_type', params.entry_type)
    if (params.limit != null) q.set('limit', String(params.limit))
    if (params.offset != null) q.set('offset', String(params.offset))
    const qs = q.toString()
    return api.get(`/journal/${qs ? `?${qs}` : ''}`)
  },

  get(id: string): Promise<JournalEntry> {
    return api.get(`/journal/${id}`)
  },

  create(data: JournalEntryCreate): Promise<JournalEntry> {
    return api.post('/journal/', data)
  },

  update(id: string, data: JournalEntryUpdate): Promise<JournalEntry> {
    return api.put(`/journal/${id}`, data)
  },

  delete(id: string): Promise<void> {
    return api.delete(`/journal/${id}`)
  },

  uploadScreenshot(id: string, file: File): Promise<JournalEntry> {
    const form = new FormData()
    form.append('file', file)
    return api.postForm(`/journal/${id}/screenshots`, form)
  },

  deleteScreenshot(id: string, filename: string): Promise<JournalEntry> {
    return api.delete(`/journal/${id}/screenshots/${filename}`)
  },

  analytics(): Promise<EmotionAnalytics> {
    return api.get('/journal/analytics/emotions')
  },
}
