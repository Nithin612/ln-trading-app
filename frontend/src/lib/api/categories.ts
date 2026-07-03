import { api } from './client'
import type { StockListResponse } from './stocks'

export interface Category {
  id: number
  name: string
  slug: string
  description: string | null
  created_by: number | null
  created_at: string
}

export interface CategoryWithCount extends Category {
  stock_count: number
}

export interface StockTagRead {
  stock_id: number
  category_id: number
  tagged_at: string
  tagged_by: number | null
}

export const categoriesApi = {
  list: (token: string) =>
    api.get<CategoryWithCount[]>('/categories', token),

  get: (id: number, token: string) =>
    api.get<CategoryWithCount>(`/categories/${id}`, token),

  create: (name: string, description: string | null, token: string) =>
    api.post<Category>('/categories', { name, description }, token),

  update: (
    id: number,
    payload: { name?: string; description?: string | null },
    token: string,
  ) => api.put<Category>(`/categories/${id}`, payload, token),

  delete: (id: number, token: string) =>
    api.delete<void>(`/categories/${id}`, token),

  getStocks: (id: number, page: number, token: string) =>
    api.get<StockListResponse>(
      `/categories/${id}/stocks?page=${page}&page_size=50`,
      token,
    ),

  getStockCategories: (stockId: number, token: string) =>
    api.get<CategoryWithCount[]>(`/stocks/${stockId}/categories`, token),

  tagStock: (stockId: number, categoryId: number, token: string) =>
    api.post<StockTagRead>(
      `/stocks/${stockId}/categories`,
      { category_id: categoryId },
      token,
    ),

  untagStock: (stockId: number, categoryId: number, token: string) =>
    api.delete<void>(`/stocks/${stockId}/categories/${categoryId}`, token),
}
