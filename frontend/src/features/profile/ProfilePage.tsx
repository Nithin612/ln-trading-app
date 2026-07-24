import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  User, Mail, Shield, TrendingUp, IndianRupee, Percent, AlertTriangle,
  Calendar, Clock, Activity, Pencil, Save, X,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/lib/api/auth'
import { usersApi } from '@/lib/api/users'
import { PageHeader } from '@/components/layout/PageHeader'
import { UserAvatar } from '@/components/ui/user-avatar'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { useToast } from '@/hooks/useToast'
import { formatCurrency, formatInt } from '@/lib/format'

// Bounds mirror backend UserUpdate (app/schemas/user.py) so client-side
// validation matches the API's.
const BOUNDS = {
  risk: { min: 0.1, max: 10 },
  loss: { min: 0.1, max: 20 },
  trades: { min: 1, max: 20 },
} as const

function InfoRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-(--color-border) last:border-0">
      <span className="text-(--color-text-muted) flex-shrink-0">{icon}</span>
      <span className="text-sm text-(--color-text-muted) w-44 flex-shrink-0">{label}</span>
      <span className="text-sm font-medium text-(--color-text)">{value}</span>
    </div>
  )
}

function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="bg-(--color-surface-3) border border-(--color-border) rounded-lg p-4 text-center">
      <div className="text-lg font-bold font-mono text-(--color-accent)">{value}</div>
      <div className="text-xs text-(--color-text-muted) mt-1">{label}</div>
      {sub && <div className="text-xs text-(--color-text-muted) mt-0.5 opacity-60">{sub}</div>}
    </div>
  )
}

interface EditableUser {
  id: number
  capital_inr: string
  risk_per_trade_pct: string
  daily_loss_limit_pct: string
  max_trades_per_day: number
  allow_offmarket_entry: boolean
}

function TradingSettingsCard({ user }: { user: EditableUser }) {
  const { accessToken } = useAuth()
  const setAuth = useAuthStore((s) => s.setAuth)
  const qc = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [capital, setCapital] = useState(user.capital_inr)
  const [risk, setRisk] = useState(user.risk_per_trade_pct)
  const [loss, setLoss] = useState(user.daily_loss_limit_pct)
  const [trades, setTrades] = useState(String(user.max_trades_per_day))
  const [offmkt, setOffmkt] = useState(user.allow_offmarket_entry)

  function reset() {
    setCapital(user.capital_inr)
    setRisk(user.risk_per_trade_pct)
    setLoss(user.daily_loss_limit_pct)
    setTrades(String(user.max_trades_per_day))
    setOffmkt(user.allow_offmarket_entry)
    setEditing(false)
  }

  const capitalN = parseFloat(capital)
  const riskN = parseFloat(risk)
  const lossN = parseFloat(loss)
  const tradesN = parseInt(trades, 10)

  const errors: string[] = []
  if (!(capitalN > 0)) errors.push('Capital must be greater than ₹0.')
  if (!(riskN >= BOUNDS.risk.min && riskN <= BOUNDS.risk.max))
    errors.push(`Risk per trade must be ${BOUNDS.risk.min}–${BOUNDS.risk.max}%.`)
  if (!(lossN >= BOUNDS.loss.min && lossN <= BOUNDS.loss.max))
    errors.push(`Daily loss limit must be ${BOUNDS.loss.min}–${BOUNDS.loss.max}%.`)
  if (!(Number.isInteger(tradesN) && tradesN >= BOUNDS.trades.min && tradesN <= BOUNDS.trades.max))
    errors.push(`Max trades/day must be a whole number ${BOUNDS.trades.min}–${BOUNDS.trades.max}.`)
  const valid = errors.length === 0

  const mutation = useMutation({
    mutationFn: () =>
      usersApi.update(accessToken!, user.id, {
        capital_inr: capital,
        risk_per_trade_pct: risk,
        daily_loss_limit_pct: loss,
        max_trades_per_day: tradesN,
        allow_offmarket_entry: offmkt,
      }),
    onSuccess: (updated) => {
      if (accessToken) setAuth(accessToken, updated)
      void qc.invalidateQueries({ queryKey: ['me'] })
      void qc.invalidateQueries({ queryKey: ['paper-record'] })
      toast.success('Trading settings updated')
      setEditing(false)
    },
    onError: (err: { message?: string }) => toast.error(err.message ?? 'Update failed'),
  })

  // Live risk preview from the current (possibly unsaved) inputs.
  const riskAmt = capitalN > 0 && riskN > 0 ? formatCurrency((capitalN * riskN) / 100) : '—'
  const lossAmt = capitalN > 0 && lossN > 0 ? formatCurrency((capitalN * lossN) / 100) : '—'

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-(--color-text)">Trading Settings</h3>
          <p className="text-xs text-(--color-text-muted) mt-0.5">
            Capital and risk — position sizes are computed from these.
          </p>
        </div>
        {!editing ? (
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Pencil size={13} /> Edit
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={reset} disabled={mutation.isPending}>
              <X size={13} /> Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => mutation.mutate()}
              disabled={!valid || mutation.isPending}
            >
              <Save size={13} /> {mutation.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        )}
      </div>

      {!editing ? (
        <div className="space-y-0">
          <InfoRow icon={<IndianRupee size={15} />} label="Capital" value={formatCurrency(capitalN)} />
          <InfoRow icon={<Percent size={15} />} label="Risk per trade"
            value={`${user.risk_per_trade_pct}%  ≈ ${riskAmt}`} />
          <InfoRow icon={<AlertTriangle size={15} />} label="Daily loss limit"
            value={`${user.daily_loss_limit_pct}%  ≈ ${lossAmt}`} />
          <InfoRow icon={<Clock size={15} />} label="Max trades / day"
            value={user.max_trades_per_day} />
          <InfoRow icon={<Activity size={15} />} label="Off-market entry"
            value={user.allow_offmarket_entry ? 'Allowed' : 'Blocked (needs live price)'} />
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="capital">Capital (₹)</Label>
              <Input id="capital" type="number" inputMode="numeric" min={1} step={1000}
                value={capital} onChange={(e) => setCapital(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="risk">Risk / trade (%)</Label>
              <Input id="risk" type="number" inputMode="decimal"
                min={BOUNDS.risk.min} max={BOUNDS.risk.max} step={0.1}
                value={risk} onChange={(e) => setRisk(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="loss">Daily loss limit (%)</Label>
              <Input id="loss" type="number" inputMode="decimal"
                min={BOUNDS.loss.min} max={BOUNDS.loss.max} step={0.1}
                value={loss} onChange={(e) => setLoss(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="trades">Max trades / day</Label>
              <Input id="trades" type="number" inputMode="numeric"
                min={BOUNDS.trades.min} max={BOUNDS.trades.max} step={1}
                value={trades} onChange={(e) => setTrades(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-(--color-text-muted)">
            <span>Risk / trade ≈ <span className="text-(--color-text) font-medium">{riskAmt}</span></span>
            <span>Daily loss cap ≈ <span className="text-(--color-text) font-medium">{lossAmt}</span></span>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <Checkbox id="offmkt" checked={offmkt} onCheckedChange={(v) => setOffmkt(!!v)} />
            <Label htmlFor="offmkt" className="cursor-pointer text-sm text-(--color-text)">
              Allow off-market entry
            </Label>
          </div>
          <p className="text-xs text-(--color-text-muted)">
            When off (recommended), paper orders are rejected unless the stock has a live price —
            prevents fills at a stale prior close.
          </p>
          {!valid && (
            <ul className="text-xs text-(--color-loss) space-y-0.5" role="alert">
              {errors.map((msg) => <li key={msg}>{msg}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export function ProfilePage() {
  const { accessToken, user: storeUser, isAdmin } = useAuth()

  const { data: user, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => authApi.me(accessToken!),
    enabled: !!accessToken,
    initialData: storeUser ?? undefined,
  })

  if (isLoading && !user) {
    return (
      <div className="max-w-2xl space-y-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!user) return null

  const joinedDate = new Date(user.created_at).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata',
  })
  const capital = formatInt(parseFloat(user.capital_inr))
  const riskAmount = formatInt(parseFloat(user.capital_inr) * parseFloat(user.risk_per_trade_pct) / 100)

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="My Profile" subtitle="Account details and trading parameters" />

      {/* Avatar + identity card */}
      <div className="card flex items-start gap-5">
        <UserAvatar name={user.full_name} size="lg" className="w-16 h-16 !text-xl" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-xl font-bold text-(--color-text)">{user.full_name}</h2>
            {isAdmin && (
              <Badge className="bg-(--color-accent-bg) text-(--color-accent) border border-(--color-accent) text-xs flex items-center gap-1">
                <Shield size={10} />
                Admin
              </Badge>
            )}
          </div>
          <p className="text-sm text-(--color-text-muted) mt-0.5">{user.email}</p>
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <span
              className="text-xs font-semibold px-2.5 py-1 rounded-full border"
              style={{
                backgroundColor: user.trading_mode === 'live' ? 'var(--color-profit-bg)' : 'var(--color-accent-bg)',
                color: user.trading_mode === 'live' ? 'var(--color-profit)' : 'var(--color-accent)',
                borderColor: user.trading_mode === 'live' ? 'var(--color-profit)' : 'var(--color-accent)',
              }}
            >
              {user.trading_mode === 'live' ? '● Live Trading' : '● Paper Trading'}
            </span>
            <span
              className="text-xs font-semibold px-2.5 py-1 rounded-full border"
              style={{
                backgroundColor: user.is_active ? 'var(--color-profit-bg)' : 'var(--color-loss-bg)',
                color: user.is_active ? 'var(--color-profit)' : 'var(--color-loss)',
                borderColor: user.is_active ? 'var(--color-profit)' : 'var(--color-loss)',
              }}
            >
              {user.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>
      </div>

      {/* Trading parameters at a glance */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard
          label="Trading Capital"
          value={`₹${capital}`}
        />
        <StatCard
          label="Risk / Trade"
          value={`${user.risk_per_trade_pct}%`}
          sub={`≈ ₹${riskAmount}`}
        />
        <StatCard
          label="Max Trades / Day"
          value={user.max_trades_per_day}
        />
      </div>

      {/* Detail rows */}
      <div className="card py-0 px-0 overflow-hidden">
        <p className="text-xs font-semibold text-(--color-text-muted) uppercase tracking-wide px-5 pt-4 pb-2">
          Account Details
        </p>
        <div className="px-5 pb-2">
          <InfoRow icon={<User size={15} />} label="Full name" value={user.full_name} />
          <InfoRow icon={<Mail size={15} />} label="Email" value={user.email} />
          <InfoRow icon={<Shield size={15} />} label="Role" value={
            <span className="capitalize">{user.role}</span>
          } />
          <InfoRow icon={<Activity size={15} />} label="Account status" value={
            <span style={{ color: user.is_active ? 'var(--color-bull)' : 'var(--color-bear)' }}>
              {user.is_active ? 'Active' : 'Inactive'}
            </span>
          } />
          <InfoRow icon={<TrendingUp size={15} />} label="Trading mode" value={
            <span className="capitalize">{user.trading_mode}</span>
          } />
          <InfoRow icon={<Calendar size={15} />} label="Member since" value={joinedDate} />
        </div>

      </div>

      <TradingSettingsCard user={user} />
    </div>
  )
}
