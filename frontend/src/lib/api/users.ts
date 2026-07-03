import { api } from './client'
import type { UserOut } from './auth'

export interface PaginatedUsers {
  items: UserOut[]
  total: number
  page: number
  size: number
  pages: number
}

export interface UserCreate {
  email: string
  password: string
  full_name: string
}

export interface UserUpdate {
  full_name?: string
  role?: string
}

export const usersApi = {
  list: (token: string, page = 1, size = 20) =>
    api.get<PaginatedUsers>(`/users?page=${page}&size=${size}`, token),

  get: (token: string, id: number) => api.get<UserOut>(`/users/${id}`, token),

  create: (token: string, body: UserCreate) =>
    api.post<UserOut>('/users', body, token),

  update: (token: string, id: number, body: UserUpdate) =>
    api.patch<UserOut>(`/users/${id}`, body, token),

  deactivate: (token: string, id: number) =>
    api.delete<{ message: string }>(`/users/${id}`, token),
}
