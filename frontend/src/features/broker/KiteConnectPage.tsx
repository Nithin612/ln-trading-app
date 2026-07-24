import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Zap, Clock, Activity, Hash, RefreshCw } from 'lucide-react'
import { brokerApi } from '../../lib/api/broker'
import { useAuth } from '../../hooks/useAuth'
import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/button'
import { Badge } from '../../components/ui/badge'
import { Skeleton } from '../../components/ui/skeleton'
import { useToast } from '../../hooks/useToast'

function formatCountdown(expiresAt: string | null | undefined): string {
  if (!expiresAt) return '—'
  const diff = new Date(expiresAt).getTime() - Date.now()
  if (diff <= 0) return 'Expired'
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function useCountdown(expiresAt: string | null | undefined) {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!expiresAt) return
    const t = setInterval(() => setTick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [expiresAt])
  // tick forces re-render; formatCountdown is pure
  void tick
  return formatCountdown(expiresAt)
}

interface HealthCardProps {
  icon: React.ReactNode
  label: string
  value: React.ReactNode
  sub?: string
}

function HealthCard({ icon, label, value, sub }: HealthCardProps) {
  return (
    <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4 flex items-start gap-3">
      <div className="w-8 h-8 rounded-md bg-(--color-surface-3) flex items-center justify-center flex-shrink-0 text-(--color-text-muted)">
        {icon}
      </div>
      <div>
        <p className="text-xs text-(--color-text-muted) uppercase tracking-wide">{label}</p>
        <div className="text-base font-semibold font-mono text-(--color-text) mt-0.5">{value}</div>
        {sub && <p className="text-xs text-(--color-text-muted) mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function KiteConnectPage() {
  const { accessToken } = useAuth()
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestToken = searchParams.get('request_token')
  const queryClient = useQueryClient()

  const { data: status, isLoading } = useQuery({
    queryKey: ['kite-status'],
    queryFn: () => brokerApi.getKiteStatus(accessToken!),
    enabled: !!accessToken,
    refetchInterval: 30_000,
  })

  const countdown = useCountdown(status?.expires_at)

  const exchangeMutation = useMutation({
    mutationFn: (token: string) => brokerApi.exchangeKiteToken(token, accessToken!),
    onSuccess: (data) => {
      toast.success(`Connected. Token valid until ${new Date(data.expires_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST`)
      setSearchParams({})
      void queryClient.invalidateQueries({ queryKey: ['kite-status'] })
    },
    onError: (e: Error) => toast.error(`Exchange failed: ${e.message}`),
  })

  useEffect(() => {
    if (requestToken && accessToken && !exchangeMutation.isPending) {
      exchangeMutation.mutate(requestToken)
    }
  }, [requestToken, accessToken]) // eslint-disable-line react-hooks/exhaustive-deps

  const loginMutation = useMutation({
    mutationFn: () => brokerApi.getKiteLoginUrl(accessToken!),
    onSuccess: (data) => { window.location.href = data.login_url },
    onError: (e: Error) => toast.error(e.message),
  })

  const syncMutation = useMutation({
    mutationFn: () => brokerApi.syncKiteInstruments(accessToken!),
    onSuccess: (r) => toast.success(`Synced ${r.synced} instruments`),
    onError: (e: Error) => toast.error(`Sync failed: ${e.message}`),
  })

  const consumerStartMutation = useMutation({
    mutationFn: () => brokerApi.startConsumer(accessToken!),
    onSuccess: () => {
      toast.success('Tick consumer started')
      void queryClient.invalidateQueries({ queryKey: ['kite-status'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const consumerStopMutation = useMutation({
    mutationFn: () => brokerApi.stopConsumer(accessToken!),
    onSuccess: () => {
      toast.success('Tick consumer stopped')
      void queryClient.invalidateQueries({ queryKey: ['kite-status'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Zerodha Kite Connect" subtitle="Live market data via Kite WebSocket" />

      {/* ── Connection status ── */}
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4 space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-(--color-text-muted)">Broker connection</span>
          {isLoading ? (
            <Skeleton className="h-5 w-24" />
          ) : status?.connected ? (
            <Badge className="bg-(--color-profit-bg) text-(--color-profit) border border-(--color-profit)/30">Connected</Badge>
          ) : (
            <Badge className="bg-(--color-loss-bg) text-(--color-loss) border border-(--color-loss)/30">Not connected</Badge>
          )}
        </div>

        {status?.connected && status.expires_at && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-(--color-text-muted)">Token expires</span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-(--color-text) tabular-nums">{countdown}</span>
              <span className="text-xs text-(--color-text-muted)">
                ({new Date(status.expires_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })} IST)
              </span>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-(--color-text-muted)">Tick consumer</span>
          {status?.consumer_running ? (
            <Badge className="bg-(--color-profit-bg) text-(--color-profit) border border-(--color-profit)/30">Running</Badge>
          ) : (
            <Badge className="bg-(--color-surface-3) text-(--color-text-muted) border border-(--color-border)">Stopped</Badge>
          )}
        </div>
      </div>

      {/* ── Consumer health (placeholders) ── */}
      <div>
        <p className="text-xs font-semibold text-(--color-text-muted) uppercase tracking-wide mb-3">Consumer Health</p>
        <div className="grid grid-cols-3 gap-3">
          <HealthCard
            icon={<Clock size={16} />}
            label="Last tick"
            value="—"
            sub="coming soon"
          />
          <HealthCard
            icon={<Activity size={16} />}
            label="Ticks today"
            value="—"
            sub="coming soon"
          />
          <HealthCard
            icon={<Hash size={16} />}
            label="Subscribed"
            value="—"
            sub="symbols"
          />
        </div>
      </div>

      {/* ── Actions ── */}
      <div className="flex flex-wrap gap-3">
        {!status?.connected && (
          <Button
            onClick={() => loginMutation.mutate()}
            disabled={loginMutation.isPending}
            className="bg-(--color-accent) hover:bg-(--color-accent-hover) text-(--color-primary-foreground)"
          >
            <Zap size={14} className="mr-1.5" />
            {loginMutation.isPending ? 'Redirecting…' : 'Connect to Zerodha'}
          </Button>
        )}

        {status?.connected && (
          <>
            <Button
              variant="outline"
              onClick={() => loginMutation.mutate()}
              disabled={loginMutation.isPending}
              className="border-(--color-border) text-(--color-text-muted) hover:bg-(--color-surface-3)"
            >
              <RefreshCw size={14} className="mr-1.5" />
              Re-authenticate
            </Button>

            <Button
              variant="outline"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="border-(--color-border) text-(--color-text-muted) hover:bg-(--color-surface-3)"
            >
              {syncMutation.isPending ? 'Syncing…' : 'Sync Instruments'}
            </Button>

            {!status.consumer_running ? (
              <Button
                variant="outline"
                onClick={() => consumerStartMutation.mutate()}
                disabled={consumerStartMutation.isPending}
                className="border-(--color-border) text-(--color-text-muted) hover:bg-(--color-surface-3)"
              >
                Start Tick Consumer
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={() => consumerStopMutation.mutate()}
                disabled={consumerStopMutation.isPending}
                className="border-(--color-border) text-(--color-text-muted) hover:bg-(--color-surface-3)"
              >
                Stop Tick Consumer
              </Button>
            )}
          </>
        )}
      </div>

      {/* ── Setup checklist ── */}
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4 space-y-2">
        <p className="text-sm font-medium text-(--color-text)">Setup checklist</p>
        <ol className="text-xs text-(--color-text-muted) space-y-1.5 list-decimal list-inside">
          <li>
            Update Zerodha Kite developer app redirect URL to:{' '}
            <code className="font-mono text-(--color-accent)">http://localhost:8000/api/v1/broker/kite/callback</code>
          </li>
          <li>Click "Connect to Zerodha" above and log in with your Zerodha credentials</li>
          <li>Click "Sync Instruments" to download symbol → token mapping (needed for tick subscription)</li>
          <li>Click "Start Tick Consumer" to begin receiving live price ticks via WebSocket</li>
          <li>Live LTP will appear on the Dashboard and Stock Detail pages</li>
        </ol>
      </div>
    </div>
  )
}
