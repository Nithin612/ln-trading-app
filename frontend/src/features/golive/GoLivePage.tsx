import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Rocket, Flame, Trophy, CheckCircle2, Circle, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi } from '@/lib/api/trading'
import { useTradingHaltStore } from '@/store/tradingHaltStore'
import { PageHeader } from '@/components/layout/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/useToast'
import { formatCurrency, formatPct } from '@/lib/format'

function Check({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 py-1.5">
      <span className="flex-shrink-0 mt-0.5" style={{ color: ok ? 'var(--color-profit)' : 'var(--color-text-muted)' }}>
        {ok ? <CheckCircle2 size={15} /> : <Circle size={15} />}
      </span>
      <span className="text-sm text-(--color-text)">{children}</span>
    </li>
  )
}

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: 'bull' | 'bear' }) {
  const color = tone === 'bull' ? 'var(--color-bull)' : tone === 'bear' ? 'var(--color-bear)' : 'var(--color-text)'
  return (
    <div>
      <div className="text-lg font-bold font-mono tabular-nums" style={{ color }}>{value}</div>
      <div className="text-[10px] text-(--color-text-muted) uppercase tracking-wide mt-0.5">{label}</div>
    </div>
  )
}

function KillSwitch() {
  const { halted, setHalted } = useTradingHaltStore()
  const toast = useToast()
  const [confirmRelease, setConfirmRelease] = useState(false)

  if (halted) {
    return (
      <div className="rounded-lg p-4 border" style={{ background: 'var(--color-loss-bg)', borderColor: 'var(--color-loss)' }}>
        <div className="flex items-center gap-2 mb-1">
          <ShieldAlert size={16} style={{ color: 'var(--color-loss)' }} />
          <span className="text-sm font-bold" style={{ color: 'var(--color-loss)' }}>TRADING HALTED</span>
        </div>
        <p className="text-xs text-(--color-text-muted) mb-3">
          New paper orders are blocked across the app. Auto-exits (monitor) still run.
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (!confirmRelease) { setConfirmRelease(true); return }
            setHalted(false); setConfirmRelease(false); toast.success('Trading resumed')
          }}
        >
          {confirmRelease ? 'Click again to confirm release' : 'Release halt'}
        </Button>
      </div>
    )
  }

  return (
    <div className="rounded-lg p-4 border border-(--color-border) bg-(--color-surface-3)">
      <div className="flex items-center gap-2 mb-1">
        <ShieldCheck size={16} style={{ color: 'var(--color-profit)' }} />
        <span className="text-sm font-semibold text-(--color-text)">Trading active</span>
      </div>
      <p className="text-xs text-(--color-text-muted) mb-3">
        Kill switch is a client-side halt on new paper orders. The live-order kill switch is Phase-7 backend.
      </p>
      <Button
        variant="destructive"
        size="sm"
        onClick={() => { setHalted(true); toast.warning('Trading halted — new orders blocked') }}
      >
        <ShieldAlert size={14} /> Halt trading
      </Button>
    </div>
  )
}

export function GoLivePage() {
  const { user, accessToken } = useAuth()

  const { data, isLoading } = useQuery({
    queryKey: ['paper-record'],
    queryFn: () => tradingApi.getPaperRecord(accessToken!),
    enabled: !!accessToken,
    refetchInterval: 60_000,
  })

  const target = data?.target_days ?? 30
  const profitable = data?.profitable_days ?? 0
  const eligible = profitable >= target
  const progressPct = Math.min(100, (profitable / target) * 100)
  const totalPnl = parseFloat(data?.total_realized_pnl ?? '0')

  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      <PageHeader title="Go Live" subtitle="30 profitable paper days are required before live orders are enabled (Phase 7)." />

      {/* Gate progress */}
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            <Rocket size={14} /> 30-day paper gate
          </span>
          <span
            className="text-[11px] font-bold px-2 py-0.5 rounded-full"
            style={{
              background: eligible ? 'var(--color-profit-bg)' : 'var(--color-accent-bg)',
              color: eligible ? 'var(--color-profit)' : 'var(--color-accent)',
            }}
          >
            {eligible ? 'CRITERIA MET' : 'IN PROGRESS'}
          </span>
        </div>

        {isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <>
            <div className="grid grid-cols-4 gap-3 mb-3">
              <Stat label="Profit days" value={`${profitable}/${target}`} />
              <Stat
                label="Streak"
                value={<span className="inline-flex items-center gap-1"><Flame size={13} />{data?.current_streak ?? 0}</span>}
                tone={(data?.current_streak ?? 0) > 0 ? 'bull' : undefined}
              />
              <Stat label="Net P&L" value={`${totalPnl >= 0 ? '+' : ''}${formatCurrency(totalPnl)}`} tone={totalPnl >= 0 ? 'bull' : 'bear'} />
              <Stat label="Win rate" value={formatPct(parseFloat(data?.win_rate_pct ?? '0'), { signed: false })} />
            </div>
            <div className="mb-1 flex justify-between text-[10px] text-(--color-text-muted)">
              <span>{profitable} of {target} profitable days</span>
              <span className="inline-flex items-center gap-1"><Trophy size={10} /> best {data?.best_streak ?? 0}</span>
            </div>
            <div className="h-2 bg-(--color-surface-3) rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${progressPct}%`, background: 'var(--color-profit)' }} />
            </div>
            {!eligible && (
              <p className="text-xs text-(--color-text-muted) mt-2">
                {target - profitable} more profitable day{target - profitable !== 1 ? 's' : ''} to go.
              </p>
            )}
          </>
        )}
      </div>

      {/* Requirements */}
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted) mb-2">Requirements before live</p>
        <ul>
          <Check ok={eligible}>30 profitable paper days ({profitable}/{target})</Check>
          <Check ok={user?.trading_mode === 'paper'}>Currently in paper mode (live requires explicit opt-in)</Check>
          <Check ok={false}>Static IP / VPS runbook — planned Phase 7</Check>
          <Check ok={false}>Live orders behind trading_mode + reconciliation — planned Phase 7</Check>
        </ul>
        <p className="text-[11px] text-(--color-text-muted) mt-2">
          This view surfaces the paper record; the 30-day gate is not yet auto-enforced in code (the enforcement,
          reconciliation, and live-order path are Phase-7 hardening).
        </p>
      </div>

      {/* Kill switch */}
      <KillSwitch />
    </div>
  )
}
