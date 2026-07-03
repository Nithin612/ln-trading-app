import { useQuery } from '@tanstack/react-query'
import {
  User, Mail, Shield, TrendingUp, IndianRupee, Percent, AlertTriangle,
  Calendar, Clock, Activity,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { authApi } from '@/lib/api/auth'
import { PageHeader } from '@/components/layout/PageHeader'
import { UserAvatar } from '@/components/ui/user-avatar'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

function InfoRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-[--color-border] last:border-0">
      <span className="text-[--color-text-muted] flex-shrink-0">{icon}</span>
      <span className="text-sm text-[--color-text-muted] w-44 flex-shrink-0">{label}</span>
      <span className="text-sm font-medium text-[--color-text]">{value}</span>
    </div>
  )
}

function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="bg-[--color-surface-3] border border-[--color-border] rounded-lg p-4 text-center">
      <div className="text-lg font-bold font-mono text-[--color-accent]">{value}</div>
      <div className="text-xs text-[--color-text-muted] mt-1">{label}</div>
      {sub && <div className="text-xs text-[--color-text-muted] mt-0.5 opacity-60">{sub}</div>}
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
  const capital = parseFloat(user.capital_inr).toLocaleString('en-IN', { maximumFractionDigits: 0 })
  const riskAmount = (parseFloat(user.capital_inr) * parseFloat(user.risk_per_trade_pct) / 100)
    .toLocaleString('en-IN', { maximumFractionDigits: 0 })

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="My Profile" subtitle="Account details and trading parameters" />

      {/* Avatar + identity card */}
      <div className="card flex items-start gap-5">
        <UserAvatar name={user.full_name} size="lg" className="w-16 h-16 !text-xl" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-xl font-bold text-[--color-text]">{user.full_name}</h2>
            {isAdmin && (
              <Badge className="bg-purple-900/40 text-purple-300 border border-purple-700 text-xs flex items-center gap-1">
                <Shield size={10} />
                Admin
              </Badge>
            )}
          </div>
          <p className="text-sm text-[--color-text-muted] mt-0.5">{user.email}</p>
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <span
              className="text-xs font-semibold px-2.5 py-1 rounded-full border"
              style={{
                backgroundColor: user.trading_mode === 'live' ? 'rgba(34,197,94,0.15)' : 'rgba(59,130,246,0.15)',
                color: user.trading_mode === 'live' ? 'var(--color-bull)' : 'var(--color-accent)',
                borderColor: user.trading_mode === 'live' ? 'rgba(34,197,94,0.3)' : 'rgba(59,130,246,0.3)',
              }}
            >
              {user.trading_mode === 'live' ? '● Live Trading' : '● Paper Trading'}
            </span>
            <span
              className="text-xs font-semibold px-2.5 py-1 rounded-full border"
              style={{
                backgroundColor: user.is_active ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                color: user.is_active ? 'var(--color-bull)' : 'var(--color-bear)',
                borderColor: user.is_active ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)',
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
        <p className="text-xs font-semibold text-[--color-text-muted] uppercase tracking-wide px-5 pt-4 pb-2">
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

        <div className="border-t border-[--color-border] mx-5" />

        <p className="text-xs font-semibold text-[--color-text-muted] uppercase tracking-wide px-5 pt-4 pb-2">
          Risk Parameters
        </p>
        <div className="px-5 pb-4">
          <InfoRow icon={<IndianRupee size={15} />} label="Capital (INR)" value={`₹${capital}`} />
          <InfoRow icon={<Percent size={15} />} label="Risk per trade" value={`${user.risk_per_trade_pct}% ≈ ₹${riskAmount}`} />
          <InfoRow icon={<AlertTriangle size={15} />} label="Daily loss limit" value={`${user.daily_loss_limit_pct}%`} />
          <InfoRow icon={<Clock size={15} />} label="Max trades / day" value={user.max_trades_per_day} />
        </div>
      </div>

      <p className="text-xs text-[--color-text-muted] text-center">
        To update your profile or risk parameters, contact your admin.
      </p>
    </div>
  )
}
