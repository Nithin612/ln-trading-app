import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, X, Edit2, UserCheck, UserX } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { usersApi } from '@/lib/api/users'
import { ApiError } from '@/lib/api/client'
import { useAuth } from '@/hooks/useAuth'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { SkeletonTable } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { SimpleSelect } from '@/components/ui/simple-select'
import { useToast } from '@/hooks/useToast'
import type { UserOut } from '@/lib/api/auth'

interface EditState {
  full_name: string
  role: string
  trading_mode: string
}

function CreateUserModal({ token, onClose }: { token: string; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => usersApi.create(token, { email, password, full_name: fullName }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User created successfully')
      onClose()
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.status === 409 ? 'A user with that email already exists.' : err.message)
      } else {
        setError('Failed to create user.')
      }
    },
  })

  function validate(): string | null {
    if (!fullName.trim()) return 'Full name is required.'
    if (!email.trim()) return 'Email is required.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Please enter a valid email address.'
    if (password.length < 8) return 'Password must be at least 8 characters.'
    if (!/[A-Z]/.test(password)) return 'Password must contain at least one uppercase letter.'
    if (!/\d/.test(password)) return 'Password must contain at least one digit.'
    return null
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center">
      <div className="card w-full max-w-[400px]">
        <h2 className="text-base font-semibold text-(--color-text) mb-5">New User</h2>
        <form onSubmit={(e) => { e.preventDefault(); const err = validate(); if (err) { setError(err); return } mutation.mutate() }}>
          <div className="space-y-3 mb-5">
            <div>
              <label className="label" htmlFor="new-name">Full name</label>
              <input id="new-name" className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="new-email">Email</label>
              <input id="new-email" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="new-password">Password</label>
              <input id="new-password" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
          </div>
          {error && <p className="error-text mb-3">{error}</p>}
          <div className="flex gap-2 justify-end">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

interface InlineUserEditProps {
  user: UserOut
  token: string
  onDone: () => void
}

function InlineUserEdit({ user, token, onDone }: InlineUserEditProps) {
  const qc = useQueryClient()
  const toast = useToast()
  const [edit, setEdit] = useState<EditState>({
    full_name: user.full_name,
    role: user.role,
    trading_mode: user.trading_mode,
  })

  const mut = useMutation({
    mutationFn: () => usersApi.update(token, user.id, { full_name: edit.full_name.trim(), role: edit.role }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      toast.success('User updated')
      onDone()
    },
    onError: (err: ApiError) => toast.error(err.message),
  })

  return (
    <>
      <td className="px-3 py-2">
        <Input
          value={edit.full_name}
          onChange={(e) => setEdit((s) => ({ ...s, full_name: e.target.value }))}
          className="h-7 text-xs bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus-visible:ring-(--color-accent) w-32"
          onKeyDown={(e) => { if (e.key === 'Enter') mut.mutate(); if (e.key === 'Escape') onDone() }}
        />
      </td>
      <td className="px-3 py-2 text-xs text-(--color-text-muted)">{user.email}</td>
      <td className="px-3 py-2">
        <SimpleSelect
          size="sm"
          value={edit.role}
          onChange={(v) => setEdit((s) => ({ ...s, role: v }))}
          options={[{ value: 'user', label: 'user' }, { value: 'admin', label: 'admin' }]}
          className="min-w-[80px]"
        />
      </td>
      <td className="px-3 py-2">
        <SimpleSelect
          size="sm"
          value={edit.trading_mode}
          onChange={(v) => setEdit((s) => ({ ...s, trading_mode: v }))}
          options={[{ value: 'paper', label: 'paper' }, { value: 'live', label: 'live' }]}
          className="min-w-[80px]"
        />
      </td>
      <td className="px-3 py-2">
        <span style={{ color: user.is_active ? 'var(--color-bull)' : 'var(--color-bear)', fontSize: '0.75rem' }}>
          {user.is_active ? 'Active' : 'Inactive'}
        </span>
      </td>
      <td className="px-3 py-2">
        <div className="flex items-center gap-1">
          <button onClick={() => mut.mutate()} disabled={mut.isPending} className="p-1.5 rounded text-(--color-bull) hover:bg-(--color-surface-3)"><Check size={13} /></button>
          <button onClick={onDone} className="p-1.5 rounded text-(--color-text-muted) hover:bg-(--color-surface-3)"><X size={13} /></button>
        </div>
      </td>
    </>
  )
}

type RoleFilter = 'ALL' | 'admin' | 'user'
type StatusFilter = 'ALL' | 'active' | 'inactive'

export function UsersPage() {
  const { accessToken } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [showCreate, setShowCreate] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('ALL')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL')

  const { data, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.list(accessToken!),
    enabled: !!accessToken,
  })

  const deactivateMut = useMutation({
    mutationFn: (id: number) => usersApi.deactivate(accessToken!, id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      toast.success('User updated')
    },
    onError: (err: ApiError) => toast.error(err.message),
  })

  const filteredUsers = (data?.items ?? []).filter((u) => {
    if (roleFilter !== 'ALL' && u.role !== roleFilter) return false
    if (statusFilter === 'active' && !u.is_active) return false
    if (statusFilter === 'inactive' && u.is_active) return false
    return true
  })

  const filterBtnCls = (active: boolean) =>
    `px-2.5 py-1 text-xs font-medium transition-colors ${
      active ? 'bg-(--color-accent) text-white' : 'bg-(--color-surface-3) text-(--color-text-muted) hover:text-(--color-text)'
    }`

  return (
    <>
      <PageHeader
        title="User Management"
        subtitle={data ? `${data.total} users total` : undefined}
        actions={
          <button className="btn btn-primary" onClick={() => setShowCreate(true)} type="button">
            New user
          </button>
        }
      />

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center mb-4">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-(--color-text-muted)">Role:</span>
          <div className="flex rounded overflow-hidden border border-(--color-border)">
            {(['ALL', 'admin', 'user'] as RoleFilter[]).map((r) => (
              <button key={r} onClick={() => setRoleFilter(r)} className={filterBtnCls(roleFilter === r)}>{r}</button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-(--color-text-muted)">Status:</span>
          <div className="flex rounded overflow-hidden border border-(--color-border)">
            {(['ALL', 'active', 'inactive'] as StatusFilter[]).map((s) => (
              <button key={s} onClick={() => setStatusFilter(s)} className={filterBtnCls(statusFilter === s)}>{s}</button>
            ))}
          </div>
        </div>
        {(roleFilter !== 'ALL' || statusFilter !== 'ALL') && (
          <button
            onClick={() => { setRoleFilter('ALL'); setStatusFilter('ALL') }}
            className="text-xs text-(--color-text-muted) hover:text-(--color-text) transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading && <SkeletonTable rows={5} cols={6} />}
      {error && (
        <p className="text-sm text-(--color-error)">
          {error instanceof ApiError ? error.message : 'Failed to load users.'}
        </p>
      )}

      {!isLoading && !error && (
        filteredUsers.length === 0 ? (
          <EmptyState title="No users" description="No users match your current filters." />
        ) : (
          <div className="rounded-lg border border-(--color-border) overflow-hidden">
            <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr className="border-b border-(--color-border) bg-(--color-surface-2) sticky top-0">
                  {['Name', 'Email', 'Role', 'Mode', 'Status', 'Actions'].map((h) => (
                    <th key={h} className="px-3 py-2.5 text-left text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted)">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="border-b border-(--color-border) hover:bg-(--color-surface-hover) transition-colors">
                    {editingId === u.id ? (
                      <InlineUserEdit user={u} token={accessToken!} onDone={() => setEditingId(null)} />
                    ) : (
                      <>
                        <td className="px-3 py-2.5 font-medium text-(--color-text)">{u.full_name}</td>
                        <td className="px-3 py-2.5 text-(--color-text-muted) text-xs">{u.email}</td>
                        <td className="px-3 py-2.5">
                          <Badge
                            className={`text-xs font-mono ${u.role === 'admin' ? 'bg-purple-900/40 text-purple-300 border-purple-700 border' : 'bg-(--color-surface-3) text-(--color-text-muted) border-(--color-border) border'}`}
                          >
                            {u.role}
                          </Badge>
                        </td>
                        <td className="px-3 py-2.5 text-(--color-text-muted) text-xs">{u.trading_mode}</td>
                        <td className="px-3 py-2.5">
                          <span
                            className="text-xs font-medium"
                            style={{ color: u.is_active ? 'var(--color-bull)' : 'var(--color-bear)' }}
                          >
                            {u.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => setEditingId(u.id)}
                              className="p-1.5 rounded text-(--color-text-muted) hover:text-(--color-accent) hover:bg-(--color-surface-3) transition-colors"
                              title="Edit user"
                            >
                              <Edit2 size={13} />
                            </button>
                            <button
                              onClick={() => deactivateMut.mutate(u.id)}
                              disabled={deactivateMut.isPending}
                              className="p-1.5 rounded text-(--color-text-muted) hover:bg-(--color-surface-3) transition-colors"
                              title={u.is_active ? 'Deactivate' : 'Activate'}
                              style={{ color: u.is_active ? 'var(--color-bear)' : 'var(--color-bull)' }}
                            >
                              {u.is_active ? <UserX size={13} /> : <UserCheck size={13} />}
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {showCreate && accessToken && (
        <CreateUserModal token={accessToken} onClose={() => setShowCreate(false)} />
      )}
    </>
  )
}
