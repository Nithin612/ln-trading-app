import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2, Play, FlaskConical, ChevronDown, ChevronUp } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import {
  strategyApi,
  type RunBacktestRequest,
  type StrategyRunOut,
  type PresetScanEntry,
} from '@/lib/api/strategy'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DateRangePicker } from '@/components/ui/date-range-picker'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { useToast } from '@/hooks/useToast'
import { EquityCurveChart } from './EquityCurveChart'

const FACTOR_GROUPS = [
  { key: 'pattern',       label: 'Pattern',       hint: 'Hammer, Engulfing, Marubozu…' },
  { key: 'trend',         label: 'Trend',         hint: 'DOW trend, EMA cross, Price vs EMA' },
  { key: 'momentum',      label: 'Momentum',      hint: 'RSI level/divergence, MACD cross/histogram' },
  { key: 'volume',        label: 'Volume',        hint: 'Volume spike, Bollinger Bands' },
  { key: 'structure',     label: 'Structure',     hint: 'S&R zones, Fibonacci, ADX' },
  { key: 'institutional', label: 'Institutional', hint: 'FII/DII flows, block deals' },
]

const UNIVERSE_OPTIONS = [
  { value: 'NIFTY50',   label: 'Nifty 50' },
  { value: 'BANKNIFTY', label: 'Bank Nifty' },
  { value: 'FNO',       label: 'F&O Stocks' },
]

const TIMEFRAME_OPTIONS = [
  { value: '1d',  label: 'Daily (1d)' },
  { value: '1h',  label: 'Hourly (1h)' },
  { value: '15m', label: '15 Minutes' },
]

const QUICK_RANGES = [
  { label: '1W',  days: 7 },
  { label: '1M',  days: 30 },
  { label: '3M',  days: 90 },
  { label: '6M',  days: 180 },
  { label: '1Y',  days: 365 },
  { label: '2Y',  days: 730 },
]

function toDateStr(d: Date): string {
  return d.toISOString().split('T')[0]
}

function today(): string { return toDateStr(new Date()) }
function daysAgo(n: number): string { return toDateStr(new Date(Date.now() - n * 86400000)) }

interface Config {
  name: string
  universe: string
  timeframe: '1d' | '1h' | '15m'
  dateRange: { from: string; to: string }
  capital: string
  riskPct: string
  minConfidence: string
  weights: Record<string, number>
}

function defaultConfig(): Config {
  return {
    name: 'Backtest run',
    universe: 'NIFTY50',
    timeframe: '1d',
    dateRange: { from: daysAgo(365), to: today() },
    capital: '100000',
    riskPct: '2',
    minConfidence: '70',
    weights: Object.fromEntries(FACTOR_GROUPS.map((g) => [g.key, 1.0])),
  }
}

function MultiplierSlider({
  value,
  onChange,
  label,
  hint,
}: {
  value: number
  onChange: (v: number) => void
  label: string
  hint: string
}) {
  const min = 0.25
  const max = 2.0
  const step = 0.25
  const pct = ((value - min) / (max - min)) * 100

  const color =
    value > 1 ? 'var(--color-bull)' : value < 1 ? 'var(--color-bear)' : 'var(--color-accent)'

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs text-(--color-text) font-medium">{label}</span>
          <span className="ml-2 text-[10px] text-(--color-text-muted)">{hint}</span>
        </div>
        <span
          className="text-xs font-mono font-bold px-1.5 py-0.5 rounded"
          style={{
            color,
            background: value === 1.0 ? 'transparent' : `color-mix(in srgb, ${color} 15%, transparent)`,
          }}
        >
          ×{value.toFixed(2)}
        </span>
      </div>
      <div className="relative h-5 flex items-center">
        <div className="w-full h-1.5 rounded-full bg-(--color-surface-3) overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${pct}%`, background: color }}
          />
        </div>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="absolute inset-0 w-full opacity-0 cursor-pointer h-full"
        />
        <div
          className="absolute w-3.5 h-3.5 rounded-full border-2 border-(--color-surface-2) shadow pointer-events-none"
          style={{ left: `calc(${pct}% - 7px)`, background: color }}
        />
      </div>
    </div>
  )
}

function numFmt(v: string | number | null | undefined, decimals = 2): string {
  if (v == null) return '—'
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (isNaN(n)) return '—'
  return n.toFixed(decimals)
}

function sharpeColor(v: string | null): string {
  if (!v) return 'var(--color-text-muted)'
  const n = parseFloat(v)
  if (n >= 1.5) return 'var(--color-bull)'
  if (n >= 0.5) return '#f59e0b'
  return 'var(--color-bear)'
}

function RunRow({
  run,
  onDelete,
  onExpand,
  expanded,
}: {
  run: StrategyRunOut
  onDelete: () => void
  onExpand: () => void
  expanded: boolean
}) {
  return (
    <>
      <tr
        className="border-b border-(--color-border) hover:bg-(--color-surface-hover) cursor-pointer"
        onClick={onExpand}
      >
        <td className="px-3 py-2 text-xs">
          <div className="font-semibold text-(--color-text)">{run.name}</div>
          <div className="text-[10px] text-(--color-text-muted)">
            {run.universe} · {run.timeframe} · {run.period_start.split('T')[0]} → {run.period_end.split('T')[0]}
          </div>
        </td>
        <td className="px-3 py-2 text-right text-xs font-mono">{run.total_trades}</td>
        <td className="px-3 py-2 text-right text-xs font-mono">
          <span style={{ color: parseFloat(run.win_rate_pct ?? '0') >= 50 ? 'var(--color-bull)' : 'var(--color-bear)' }}>
            {numFmt(run.win_rate_pct)}%
          </span>
        </td>
        <td className="px-3 py-2 text-right text-xs font-mono">
          <span style={{ color: sharpeColor(run.sharpe) }}>
            {numFmt(run.sharpe)}
          </span>
        </td>
        <td className="px-3 py-2 text-right text-xs font-mono">{numFmt(run.sortino)}</td>
        <td className="px-3 py-2 text-right text-xs font-mono">
          <span style={{ color: parseFloat(run.max_drawdown_pct ?? '0') > 15 ? 'var(--color-bear)' : 'var(--color-text)' }}>
            {numFmt(run.max_drawdown_pct)}%
          </span>
        </td>
        <td className="px-3 py-2 text-right text-xs font-mono">{numFmt(run.avg_rr)}</td>
        <td className="px-3 py-2 text-right text-xs">
          <div className="flex items-center justify-end gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="p-1 rounded hover:bg-(--color-surface-3) text-(--color-bear)"
              title="Delete run"
            >
              <Trash2 size={12} />
            </button>
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-(--color-border) bg-(--color-surface-2)">
          <td colSpan={8} className="px-4 py-3">
            <div className="flex flex-col gap-3">
              {run.equity_curve && run.equity_curve.length > 1 && (
                <EquityCurveChart data={run.equity_curve} label={run.name} />
              )}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-(--color-text-muted)">Total P&L</span>
                  <div className="font-mono font-bold" style={{ color: parseFloat(run.total_pnl_pct ?? '0') >= 0 ? 'var(--color-bull)' : 'var(--color-bear)' }}>
                    {numFmt(run.total_pnl_pct)}%
                  </div>
                </div>
                <div>
                  <span className="text-(--color-text-muted)">Avg P&L / trade</span>
                  <div className="font-mono">{numFmt(run.avg_pnl_pct)}%</div>
                </div>
                <div>
                  <span className="text-(--color-text-muted)">Avg Holding</span>
                  <div className="font-mono">{numFmt(run.avg_holding_days)} days</div>
                </div>
                <div>
                  <span className="text-(--color-text-muted)">W / L</span>
                  <div className="font-mono">
                    <span style={{ color: 'var(--color-bull)' }}>{run.winning_trades}</span>
                    {' / '}
                    <span style={{ color: 'var(--color-bear)' }}>{run.losing_trades ?? run.total_trades - run.winning_trades}</span>
                  </div>
                </div>
              </div>
              {run.factor_weights && Object.keys(run.factor_weights).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(run.factor_weights).map(([k, v]) => (
                    <span
                      key={k}
                      className="text-[10px] px-2 py-0.5 rounded-full border border-(--color-border) font-mono"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      {k} ×{(v as number).toFixed(2)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function PresetTable({ entries }: { entries: PresetScanEntry[] }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr className="border-b border-(--color-border)">
            {['Preset', 'Trades', 'Win %', 'Sharpe', 'Sortino', 'Max DD%', 'Avg RR', ''].map((h) => (
              <th
                key={h}
                className="px-3 py-2 text-[10px] uppercase tracking-wide font-medium whitespace-nowrap"
                style={{ color: 'var(--color-text-muted)', textAlign: h === 'Preset' ? 'left' : 'right' }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => (
            <>
              <tr
                key={e.preset_name}
                className="border-b border-(--color-border) hover:bg-(--color-surface-hover) cursor-pointer"
                onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
              >
                <td className="px-3 py-2 font-semibold text-(--color-text) capitalize">
                  {e.preset_name.replace(/_/g, ' ')}
                </td>
                <td className="px-3 py-2 text-right font-mono">{e.total_trades}</td>
                <td className="px-3 py-2 text-right font-mono">
                  <span style={{ color: e.win_rate_pct >= 50 ? 'var(--color-bull)' : 'var(--color-bear)' }}>
                    {e.win_rate_pct.toFixed(1)}%
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  <span style={{ color: e.sharpe >= 1 ? 'var(--color-bull)' : e.sharpe >= 0 ? '#f59e0b' : 'var(--color-bear)' }}>
                    {e.sharpe.toFixed(2)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono">{e.sortino.toFixed(2)}</td>
                <td className="px-3 py-2 text-right font-mono">
                  <span style={{ color: e.max_drawdown_pct > 15 ? 'var(--color-bear)' : 'var(--color-text)' }}>
                    {e.max_drawdown_pct.toFixed(1)}%
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono">{e.avg_rr.toFixed(2)}</td>
                <td className="px-3 py-2 text-right">
                  {expandedIdx === i ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </td>
              </tr>
              {expandedIdx === i && (
                <tr key={`${e.preset_name}-exp`} className="border-b border-(--color-border) bg-(--color-surface-2)">
                  <td colSpan={8} className="px-4 py-3">
                    {e.equity_curve.length > 1 && (
                      <EquityCurveChart data={e.equity_curve} label={e.preset_name} />
                    )}
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function StrategyLabPage() {
  const { accessToken } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()

  const [config, setConfig] = useState<Config>(defaultConfig)
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<'saved' | 'scan'>('saved')
  const [scanResults, setScanResults] = useState<PresetScanEntry[] | null>(null)

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['strategy-runs'],
    queryFn: () => strategyApi.listRuns(accessToken!),
    enabled: !!accessToken,
  })

  const runMutation = useMutation({
    mutationFn: (req: RunBacktestRequest) => strategyApi.createRun(req, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['strategy-runs'] })
      toast.success('Backtest complete')
      setActiveTab('saved')
    },
    onError: () => toast.error('Backtest failed'),
  })

  const scanMutation = useMutation({
    mutationFn: () =>
      strategyApi.presetScan(
        {
          timeframe: config.timeframe,
          universe: config.universe,
          period_start: `${config.dateRange.from}T00:00:00`,
          period_end: `${config.dateRange.to}T23:59:59`,
          capital: config.capital,
          risk_pct: config.riskPct,
          min_confidence: parseInt(config.minConfidence),
        },
        accessToken!,
      ),
    onSuccess: (data) => {
      setScanResults(data.entries)
      setActiveTab('scan')
    },
    onError: () => toast.error('Preset scan failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => strategyApi.deleteRun(id, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['strategy-runs'] })
      toast.success('Run deleted')
    },
  })

  function applyQuickRange(days: number) {
    setConfig((c) => ({ ...c, dateRange: { from: daysAgo(days), to: today() } }))
  }

  function handleRunBacktest() {
    const nonDefaultWeights = Object.fromEntries(
      Object.entries(config.weights).filter(([, v]) => v !== 1.0)
    )
    runMutation.mutate({
      name: config.name,
      timeframe: config.timeframe,
      universe: config.universe,
      period_start: `${config.dateRange.from}T00:00:00`,
      period_end: `${config.dateRange.to}T23:59:59`,
      capital: config.capital,
      risk_pct: config.riskPct,
      min_confidence: parseInt(config.minConfidence),
      weight_multipliers: nonDefaultWeights,
    })
  }

  const runs = runsData?.runs ?? []
  const isBusy = runMutation.isPending || scanMutation.isPending

  return (
    <div className="flex flex-col gap-5">
      {/* ── Config panel ── */}
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center gap-2">
          <FlaskConical size={15} style={{ color: 'var(--color-accent)' }} />
          <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            Backtest Configuration
          </span>
        </div>
        <div className="p-4 flex flex-col gap-4">
          {/* Row 1: name + universe + timeframe */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-(--color-text-muted)">Run name</Label>
              <Input
                value={config.name}
                onChange={(e) => setConfig((c) => ({ ...c, name: e.target.value }))}
                placeholder="e.g. Momentum-heavy 1Y"
                className="text-xs"
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-(--color-text-muted)">Universe</Label>
              <Select
                value={config.universe}
                onValueChange={(v) => { if (v) setConfig((c) => ({ ...c, universe: v })) }}
              >
                <SelectTrigger className="w-full bg-(--color-surface-3) border-(--color-border) text-(--color-text) text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-(--color-surface-3) border-(--color-border) text-(--color-text)">
                  {UNIVERSE_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-(--color-text-muted)">Timeframe</Label>
              <Select
                value={config.timeframe}
                onValueChange={(v) => { if (v) setConfig((c) => ({ ...c, timeframe: v as Config['timeframe'] })) }}
              >
                <SelectTrigger className="w-full bg-(--color-surface-3) border-(--color-border) text-(--color-text) text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-(--color-surface-3) border-(--color-border) text-(--color-text)">
                  {TIMEFRAME_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Row 2: date range + quick ranges */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-3 flex-wrap">
              <DateRangePicker
                value={config.dateRange}
                onChange={(r) => setConfig((c) => ({ ...c, dateRange: r }))}
                label="Period"
                maxDate={today()}
              />
              <div className="flex gap-1 mt-4">
                {QUICK_RANGES.map((qr) => (
                  <button
                    key={qr.label}
                    onClick={() => applyQuickRange(qr.days)}
                    className="text-[10px] px-2 py-1 rounded border border-(--color-border) text-(--color-text-muted) hover:bg-(--color-surface-3) hover:text-(--color-text) transition-colors"
                  >
                    {qr.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Row 3: capital + risk + confidence */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-(--color-text-muted)">Capital (₹)</Label>
              <Input
                type="number"
                value={config.capital}
                onChange={(e) => setConfig((c) => ({ ...c, capital: e.target.value }))}
                className="text-xs font-mono"
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-(--color-text-muted)">Risk per trade (%)</Label>
              <Input
                type="number"
                value={config.riskPct}
                onChange={(e) => setConfig((c) => ({ ...c, riskPct: e.target.value }))}
                min="0.1"
                max="10"
                step="0.1"
                className="text-xs font-mono"
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-(--color-text-muted)">Min confidence (%)</Label>
              <Input
                type="number"
                value={config.minConfidence}
                onChange={(e) => setConfig((c) => ({ ...c, minConfidence: e.target.value }))}
                min="0"
                max="100"
                className="text-xs font-mono"
              />
            </div>
          </div>

          {/* Row 4: factor weight sliders */}
          <div>
            <div className="text-xs font-semibold text-(--color-text-muted) uppercase tracking-wide mb-2">
              Factor weight multipliers
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {FACTOR_GROUPS.map((g) => (
                <MultiplierSlider
                  key={g.key}
                  label={g.label}
                  hint={g.hint}
                  value={config.weights[g.key] ?? 1.0}
                  onChange={(v) =>
                    setConfig((c) => ({ ...c, weights: { ...c.weights, [g.key]: v } }))
                  }
                />
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 pt-1 border-t border-(--color-border)">
            <Button
              onClick={handleRunBacktest}
              disabled={isBusy || !config.name.trim()}
              size="sm"
            >
              <Play size={13} className="mr-1.5" />
              {runMutation.isPending ? 'Running…' : 'Run Backtest'}
            </Button>
            <Button
              variant="outline"
              onClick={() => scanMutation.mutate()}
              disabled={isBusy}
              size="sm"
            >
              {scanMutation.isPending ? 'Scanning…' : 'Quick Preset Scan'}
            </Button>
            <Button
              variant="ghost"
              onClick={() => setConfig(defaultConfig())}
              disabled={isBusy}
              size="sm"
            >
              Reset
            </Button>
          </div>
        </div>
      </div>

      {/* ── Tabs: Saved runs / Preset scan ── */}
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="flex border-b border-(--color-border)">
          {(['saved', 'scan'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              className="px-5 py-3 text-xs font-semibold transition-colors border-b-2"
              style={{
                borderBottomColor: activeTab === t ? 'var(--color-accent)' : 'transparent',
                color: activeTab === t ? 'var(--color-accent)' : 'var(--color-text-muted)',
              }}
            >
              {t === 'saved' ? `Saved Runs (${runsData?.total ?? 0})` : 'Preset Scan'}
            </button>
          ))}
        </div>

        {activeTab === 'saved' && (
          <>
            {runsLoading && <div className="p-4"><Skeleton className="h-40 w-full" /></div>}
            {!runsLoading && runs.length === 0 && (
              <EmptyState
                title="No saved runs"
                description="Configure a backtest above and click Run Backtest to get started."
              />
            )}
            {!runsLoading && runs.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr className="border-b border-(--color-border)">
                      {['Run', 'Trades', 'Win %', 'Sharpe', 'Sortino', 'Max DD%', 'Avg RR', ''].map((h) => (
                        <th
                          key={h}
                          className="px-3 py-2 text-[10px] uppercase tracking-wide font-medium whitespace-nowrap"
                          style={{ color: 'var(--color-text-muted)', textAlign: h === 'Run' ? 'left' : 'right' }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <RunRow
                        key={run.id}
                        run={run}
                        expanded={expandedRunId === run.id}
                        onExpand={() =>
                          setExpandedRunId((prev) => (prev === run.id ? null : run.id))
                        }
                        onDelete={() => deleteMutation.mutate(run.id)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {activeTab === 'scan' && (
          <>
            {scanMutation.isPending && <div className="p-4"><Skeleton className="h-40 w-full" /></div>}
            {!scanMutation.isPending && !scanResults && (
              <EmptyState
                title="No scan results yet"
                description="Click Quick Preset Scan to compare all named strategies on your selected universe."
              />
            )}
            {scanResults && scanResults.length > 0 && (
              <PresetTable entries={scanResults} />
            )}
          </>
        )}
      </div>
    </div>
  )
}
