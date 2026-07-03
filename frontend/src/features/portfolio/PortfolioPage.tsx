import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  uploadCas, listBatches, getBatch, deleteBatch,
  listAssets, createAsset, updateAsset, deleteAsset, getNetWorth,
  type MfImportBatchOut, type MfHoldingOut,
  type ManualAssetOut, type ManualAssetCreate, type ManualAssetUpdate,
  type NetWorthOut,
} from '@/lib/api/portfolio'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SimpleSelect } from '@/components/ui/simple-select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Dialog } from '@/components/ui/dialog'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useToast } from '@/hooks/useToast'
import { cn } from '@/lib/utils'
import {
  UploadCloud, Trash2, Pencil, Plus, ChevronDown, ChevronRight,
  Coins, PiggyBank, TrendingUp, Wallet, RefreshCw,
} from 'lucide-react'

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmt(value: string | number, digits = 0) {
  const n = typeof value === 'string' ? parseFloat(value) : value
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function pct(a: string, total: string) {
  const n = parseFloat(a)
  const t = parseFloat(total)
  if (!t) return '0%'
  return `${((n / t) * 100).toFixed(1)}%`
}

const ASSET_TYPE_OPTS = [
  { value: 'gold',        label: 'Gold' },
  { value: 'fd',          label: 'Fixed Deposit' },
  { value: 'ppf',         label: 'PPF' },
  { value: 'nps',         label: 'NPS' },
  { value: 'bonds',       label: 'Bonds' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'other',       label: 'Other' },
]

const ASSET_TYPE_LABELS: Record<string, string> = {
  gold: 'Gold', fd: 'FD', ppf: 'PPF', nps: 'NPS',
  bonds: 'Bonds', real_estate: 'Real Estate', other: 'Other',
}

const ASSET_TYPE_COLORS: Record<string, string> = {
  gold:        'text-yellow-400',
  fd:          'text-blue-400',
  ppf:         'text-[--color-profit]',
  nps:         'text-purple-400',
  bonds:       'text-cyan-400',
  real_estate: 'text-orange-400',
  other:       'text-[--color-text-muted]',
}

// ── Net Worth Dashboard ────────────────────────────────────────────────────────

function NetWorthCard({ data }: { data: NetWorthOut }) {
  const total = parseFloat(data.total_net_worth)

  const segments = [
    {
      label: 'Equity',
      value: data.equity.current_value,
      color: 'bg-[--color-accent]',
      icon: <TrendingUp size={16} />,
      sub: `${data.equity.position_count} position${data.equity.position_count === 1 ? '' : 's'}`,
    },
    {
      label: 'Mutual Funds',
      value: data.mutual_funds.current_value,
      color: 'bg-purple-500',
      icon: <PiggyBank size={16} />,
      sub: data.mutual_funds.last_imported
        ? `${data.mutual_funds.holding_count} scheme${data.mutual_funds.holding_count === 1 ? '' : 's'}`
        : 'No import yet',
    },
    {
      label: 'Other Assets',
      value: data.manual_assets.current_value,
      color: 'bg-yellow-500',
      icon: <Coins size={16} />,
      sub: `${data.manual_assets.count} asset${data.manual_assets.count === 1 ? '' : 's'}`,
    },
  ]

  return (
    <div className="space-y-4">
      {/* Total */}
      <div
        className="rounded-xl p-6 text-center border border-[--color-border]"
        style={{ background: 'linear-gradient(135deg, var(--color-surface-2) 0%, var(--color-surface-3) 100%)' }}
      >
        <p className="text-xs text-[--color-text-muted] uppercase tracking-widest mb-1">Total Net Worth</p>
        <p className="text-4xl font-bold font-mono text-[--color-text]">{fmt(data.total_net_worth)}</p>
        <p className="text-xs text-[--color-text-muted] mt-1">
          as of {new Date(data.as_of).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' })} IST
        </p>
      </div>

      {/* Stacked bar breakdown */}
      {total > 0 && (
        <div className="h-3 rounded-full overflow-hidden flex gap-0.5">
          {segments.map((s) => {
            const w = parseFloat(pct(s.value, data.total_net_worth))
            if (w < 0.5) return null
            return (
              <div
                key={s.label}
                className={cn('h-full rounded-sm transition-all', s.color)}
                style={{ width: `${w}%` }}
                title={`${s.label}: ${fmt(s.value)}`}
              />
            )
          })}
        </div>
      )}

      {/* Segment cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {segments.map((s) => (
          <div
            key={s.label}
            className="rounded-lg p-4 border border-[--color-border] bg-[--color-surface-2] space-y-1"
          >
            <div className="flex items-center gap-2 text-[--color-text-muted] text-xs">
              {s.icon}
              <span>{s.label}</span>
            </div>
            <p className="font-mono font-semibold text-[--color-text]">{fmt(s.value)}</p>
            <p className="text-xs text-[--color-text-muted]">{total > 0 ? pct(s.value, data.total_net_worth) : '—'}</p>
            <p className="text-xs text-[--color-text-muted]">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Manual breakdown */}
      {data.manual_assets.breakdown.length > 0 && (
        <div className="rounded-lg border border-[--color-border] bg-[--color-surface-2] p-4">
          <p className="text-xs text-[--color-text-muted] uppercase tracking-widest mb-3">Other Assets Breakdown</p>
          <div className="space-y-2">
            {data.manual_assets.breakdown.map((b) => (
              <div key={b.asset_type} className="flex items-center gap-3">
                <span className={cn('text-xs font-medium w-24 truncate', ASSET_TYPE_COLORS[b.asset_type])}>
                  {b.label}
                </span>
                <div className="flex-1 h-1.5 rounded-full bg-[--color-surface-3] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[--color-accent]"
                    style={{ width: pct(b.total_value, data.manual_assets.current_value) }}
                  />
                </div>
                <span className="text-xs font-mono text-[--color-text-muted] w-28 text-right">
                  {fmt(b.total_value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── CAS Upload ─────────────────────────────────────────────────────────────────

function CasUploadZone({ onUploaded }: { onUploaded: () => void }) {
  const { success, error } = useToast()
  const fileRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadCas(file),
    onSuccess: (batch) => {
      success(`CAS imported — ${batch.total_holdings} holding${batch.total_holdings === 1 ? '' : 's'}, value: ${fmt(batch.total_value)}`)
      onUploaded()
    },
    onError: (e: Error) => error(`Upload failed: ${e.message}`),
  })

  const handleFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      error('Only PDF files accepted')
      return
    }
    uploadMut.mutate(file)
  }

  return (
    <div
      className={cn(
        'border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer',
        dragging
          ? 'border-[--color-accent] bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)]'
          : 'border-[--color-border] hover:border-[--color-accent] hover:bg-[--color-surface-2]',
      )}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) handleFile(file)
      }}
      onClick={() => fileRef.current?.click()}
    >
      <input
        ref={fileRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
          e.target.value = ''
        }}
      />
      <UploadCloud size={36} className="mx-auto text-[--color-text-muted] mb-3" />
      {uploadMut.isPending ? (
        <p className="text-sm text-[--color-text-muted]">Uploading and parsing…</p>
      ) : (
        <>
          <p className="text-sm font-medium text-[--color-text]">Drop your CAMS CAS PDF here</p>
          <p className="text-xs text-[--color-text-muted] mt-1">or click to browse · PDF only · max 20 MB</p>
        </>
      )}
    </div>
  )
}

// ── Batch list + holdings ──────────────────────────────────────────────────────

function BatchRow({ batch, onDelete }: { batch: MfImportBatchOut; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const { success } = useToast()
  const qc = useQueryClient()

  const detailQ = useQuery({
    queryKey: ['mf-batch-detail', batch.id],
    queryFn: () => getBatch(batch.id),
    enabled: expanded,
  })

  const deleteMut = useMutation({
    mutationFn: () => deleteBatch(batch.id),
    onSuccess: () => {
      success('Import deleted')
      qc.invalidateQueries({ queryKey: ['mf-batches'] })
      qc.invalidateQueries({ queryKey: ['net-worth'] })
      onDelete()
    },
  })

  return (
    <div className="border border-[--color-border] rounded-lg overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 bg-[--color-surface-2]">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 flex-1 text-left text-sm text-[--color-text] hover:text-[--color-accent] transition-colors min-w-0"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span className="font-medium truncate">{batch.source_filename}</span>
        </button>
        <span className="text-xs text-[--color-text-muted] whitespace-nowrap">
          {batch.total_holdings} scheme{batch.total_holdings === 1 ? '' : 's'}
        </span>
        <span className="text-xs font-mono font-semibold text-[--color-text] whitespace-nowrap">
          {fmt(batch.total_value)}
        </span>
        <span className="text-xs text-[--color-text-muted] whitespace-nowrap">
          {new Date(batch.created_at).toLocaleDateString('en-IN')}
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => deleteMut.mutate()}
          disabled={deleteMut.isPending}
          className="text-[--color-bear] hover:text-[--color-bear] flex-shrink-0"
          title="Delete import"
        >
          <Trash2 size={13} />
        </Button>
      </div>

      {expanded && (
        <div className="border-t border-[--color-border]">
          {!detailQ.data ? (
            <div className="p-4 space-y-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-8" />)}
            </div>
          ) : (
            <HoldingsTable holdings={detailQ.data.holdings} />
          )}
        </div>
      )}
    </div>
  )
}

function HoldingsTable({ holdings }: { holdings: MfHoldingOut[] }) {
  if (holdings.length === 0) {
    return (
      <div className="p-6 text-center text-sm text-[--color-text-muted]">
        No holdings were parsed from this import.
      </div>
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[--color-border] text-[--color-text-muted]">
            <th className="text-left px-4 py-2 font-medium">Scheme</th>
            <th className="text-left px-4 py-2 font-medium">AMC</th>
            <th className="text-left px-4 py-2 font-medium">Folio</th>
            <th className="text-right px-4 py-2 font-medium">Units</th>
            <th className="text-right px-4 py-2 font-medium">NAV</th>
            <th className="text-right px-4 py-2 font-medium">Value</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.id} className="border-b border-[--color-border] last:border-0 hover:bg-[--color-surface-2]">
              <td className="px-4 py-2 max-w-xs truncate text-[--color-text]" title={h.scheme_name}>{h.scheme_name}</td>
              <td className="px-4 py-2 text-[--color-text-muted] max-w-[120px] truncate" title={h.amc_name}>{h.amc_name}</td>
              <td className="px-4 py-2 text-[--color-text-muted] font-mono">{h.folio_number}</td>
              <td className="px-4 py-2 text-right font-mono text-[--color-text]">{parseFloat(h.units).toFixed(4)}</td>
              <td className="px-4 py-2 text-right font-mono text-[--color-text]">{fmt(h.nav, 2)}</td>
              <td className="px-4 py-2 text-right font-mono font-semibold text-[--color-text]">{fmt(h.current_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MutualFundsTab() {
  const qc = useQueryClient()
  const batchesQ = useQuery({ queryKey: ['mf-batches'], queryFn: listBatches })

  return (
    <div className="space-y-4 pt-4">
      <CasUploadZone onUploaded={() => {
        void qc.invalidateQueries({ queryKey: ['mf-batches'] })
        void qc.invalidateQueries({ queryKey: ['net-worth'] })
      }} />

      <div className="space-y-2">
        <h3 className="text-sm font-medium text-[--color-text]">Import History</h3>
        {batchesQ.isLoading ? (
          <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : !batchesQ.data?.length ? (
          <EmptyState
            icon={<PiggyBank size={32} />}
            title="No CAS imports yet"
            description="Upload your CAMS Consolidated Account Statement PDF to see your mutual fund holdings."
          />
        ) : (
          batchesQ.data.map((batch) => (
            <BatchRow key={batch.id} batch={batch} onDelete={() => void batchesQ.refetch()} />
          ))
        )}
      </div>
    </div>
  )
}

// ── Manual Assets ──────────────────────────────────────────────────────────────

interface AssetFormState {
  asset_type: string
  name: string
  institution: string
  current_value: string
  purchase_value: string
  purchase_date: string
  maturity_date: string
  units: string
  unit_price: string
  notes: string
}

const EMPTY_FORM: AssetFormState = {
  asset_type: 'gold',
  name: '',
  institution: '',
  current_value: '',
  purchase_value: '',
  purchase_date: '',
  maturity_date: '',
  units: '',
  unit_price: '',
  notes: '',
}

function AssetFormModal({
  editing,
  onClose,
  onSaved,
}: {
  editing: ManualAssetOut | null
  onClose: () => void
  onSaved: () => void
}) {
  const { success, error } = useToast()
  const [form, setForm] = useState<AssetFormState>(() =>
    editing
      ? {
          asset_type: editing.asset_type,
          name: editing.name,
          institution: editing.institution ?? '',
          current_value: editing.current_value,
          purchase_value: editing.purchase_value ?? '',
          purchase_date: editing.purchase_date ?? '',
          maturity_date: editing.maturity_date ?? '',
          units: editing.units ?? '',
          unit_price: editing.unit_price ?? '',
          notes: editing.notes ?? '',
        }
      : { ...EMPTY_FORM }
  )

  const set = (k: keyof AssetFormState, v: string) => setForm((f) => ({ ...f, [k]: v }))

  const createMut = useMutation({
    mutationFn: (p: ManualAssetCreate) => createAsset(p),
    onSuccess: () => { success('Asset added'); onSaved() },
    onError: (e: Error) => error(`Failed to save: ${e.message}`),
  })

  const updateMut = useMutation({
    mutationFn: (p: ManualAssetUpdate) => updateAsset(editing!.id, p),
    onSuccess: () => { success('Asset updated'); onSaved() },
    onError: (e: Error) => error(`Failed to update: ${e.message}`),
  })

  const isPending = createMut.isPending || updateMut.isPending
  const showMaturity = ['fd', 'ppf', 'nps', 'bonds'].includes(form.asset_type)
  const showUnits = ['gold', 'bonds'].includes(form.asset_type)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.current_value) {
      error('Name and current value are required')
      return
    }

    const base = {
      asset_type: form.asset_type,
      name: form.name.trim(),
      current_value: form.current_value,
      ...(form.institution ? { institution: form.institution } : {}),
      ...(form.purchase_value ? { purchase_value: form.purchase_value } : {}),
      ...(form.purchase_date ? { purchase_date: form.purchase_date } : {}),
      ...(form.maturity_date ? { maturity_date: form.maturity_date } : {}),
      ...(form.units ? { units: form.units } : {}),
      ...(form.unit_price ? { unit_price: form.unit_price } : {}),
      ...(form.notes ? { notes: form.notes } : {}),
    }

    if (editing) {
      updateMut.mutate(base as ManualAssetUpdate)
    } else {
      createMut.mutate(base as ManualAssetCreate)
    }
  }

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <div className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
        <h2 className="text-base font-semibold text-[--color-text]">
          {editing ? 'Edit Asset' : 'Add Asset'}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-[--color-text-muted]">Asset Type</label>
              <SimpleSelect
                value={form.asset_type}
                onChange={(v) => set('asset_type', v)}
                options={ASSET_TYPE_OPTS}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[--color-text-muted]">Name *</label>
              <Input
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                placeholder="e.g. Gold coins 10g"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-[--color-text-muted]">Current Value (₹) *</label>
              <Input
                type="number"
                value={form.current_value}
                onChange={(e) => set('current_value', e.target.value)}
                placeholder="0"
                min="0"
                step="0.01"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[--color-text-muted]">Institution</label>
              <Input
                value={form.institution}
                onChange={(e) => set('institution', e.target.value)}
                placeholder="e.g. SBI, HDFC"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-[--color-text-muted]">Purchase Value (₹)</label>
              <Input
                type="number"
                value={form.purchase_value}
                onChange={(e) => set('purchase_value', e.target.value)}
                placeholder="0"
                min="0"
                step="0.01"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[--color-text-muted]">Purchase Date</label>
              <Input
                type="date"
                value={form.purchase_date}
                onChange={(e) => set('purchase_date', e.target.value)}
              />
            </div>
          </div>

          {showMaturity && (
            <div className="space-y-1">
              <label className="text-xs text-[--color-text-muted]">Maturity Date</label>
              <Input
                type="date"
                value={form.maturity_date}
                onChange={(e) => set('maturity_date', e.target.value)}
              />
            </div>
          )}

          {showUnits && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-[--color-text-muted]">
                  {form.asset_type === 'gold' ? 'Quantity (grams)' : 'Units'}
                </label>
                <Input
                  type="number"
                  value={form.units}
                  onChange={(e) => set('units', e.target.value)}
                  placeholder="0"
                  min="0"
                  step="0.0001"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-[--color-text-muted]">
                  {form.asset_type === 'gold' ? 'Price per gram (₹)' : 'Price per unit (₹)'}
                </label>
                <Input
                  type="number"
                  value={form.unit_price}
                  onChange={(e) => set('unit_price', e.target.value)}
                  placeholder="0"
                  min="0"
                  step="0.01"
                />
              </div>
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs text-[--color-text-muted]">Notes</label>
            <Input
              value={form.notes}
              onChange={(e) => set('notes', e.target.value)}
              placeholder="Optional notes"
            />
          </div>

          <div className="flex gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
              Cancel
            </Button>
            <Button type="submit" disabled={isPending} className="flex-1">
              {isPending ? 'Saving…' : editing ? 'Save Changes' : 'Add Asset'}
            </Button>
          </div>
        </form>
      </div>
    </Dialog>
  )
}

function AssetRow({
  asset,
  onEdit,
  onDeleted,
}: {
  asset: ManualAssetOut
  onEdit: () => void
  onDeleted: () => void
}) {
  const { success } = useToast()
  const qc = useQueryClient()

  const deleteMut = useMutation({
    mutationFn: () => deleteAsset(asset.id),
    onSuccess: () => {
      success('Asset deleted')
      void qc.invalidateQueries({ queryKey: ['manual-assets'] })
      void qc.invalidateQueries({ queryKey: ['net-worth'] })
      onDeleted()
    },
  })

  const gainLoss = asset.purchase_value
    ? parseFloat(asset.current_value) - parseFloat(asset.purchase_value)
    : null

  return (
    <tr className="border-b border-[--color-border] last:border-0 hover:bg-[--color-surface-2] group">
      <td className="px-4 py-3">
        <span className={cn('text-xs font-medium', ASSET_TYPE_COLORS[asset.asset_type])}>
          {ASSET_TYPE_LABELS[asset.asset_type] ?? asset.asset_type}
        </span>
      </td>
      <td className="px-4 py-3">
        <p className="text-sm text-[--color-text]">{asset.name}</p>
        {asset.institution && (
          <p className="text-xs text-[--color-text-muted]">{asset.institution}</p>
        )}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm text-[--color-text]">
        {fmt(asset.current_value)}
      </td>
      <td className="px-4 py-3 text-right">
        {gainLoss !== null ? (
          <span className={cn('text-xs font-mono', gainLoss >= 0 ? 'text-[--color-bull]' : 'text-[--color-bear]')}>
            {gainLoss >= 0 ? '+' : ''}{fmt(gainLoss)}
          </span>
        ) : (
          <span className="text-xs text-[--color-text-muted]">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-[--color-text-muted] text-xs">
        {asset.purchase_date ?? '—'}
      </td>
      <td className="px-4 py-3 text-[--color-text-muted] text-xs">
        {asset.maturity_date ?? '—'}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button size="sm" variant="ghost" onClick={onEdit} title="Edit">
            <Pencil size={13} />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => deleteMut.mutate()}
            disabled={deleteMut.isPending}
            className="text-[--color-bear] hover:text-[--color-bear]"
            title="Delete"
          >
            <Trash2 size={13} />
          </Button>
        </div>
      </td>
    </tr>
  )
}

function ManualAssetsTab() {
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ManualAssetOut | null>(null)
  const [typeFilter, setTypeFilter] = useState('')
  const qc = useQueryClient()

  const assetsQ = useQuery({
    queryKey: ['manual-assets', typeFilter],
    queryFn: () => listAssets(typeFilter || undefined),
  })

  const closeModal = () => { setModalOpen(false); setEditing(null) }
  const onSaved = () => {
    closeModal()
    void qc.invalidateQueries({ queryKey: ['manual-assets'] })
    void qc.invalidateQueries({ queryKey: ['net-worth'] })
  }

  const totalValue = assetsQ.data?.reduce((sum, a) => sum + parseFloat(a.current_value), 0) ?? 0

  return (
    <div className="space-y-4 pt-4">
      <div className="flex items-center gap-3">
        <SimpleSelect
          value={typeFilter}
          onChange={setTypeFilter}
          options={[{ value: '', label: 'All types' }, ...ASSET_TYPE_OPTS]}
          placeholder="All types"
          className="w-44"
        />
        <div className="flex-1" />
        {assetsQ.data && assetsQ.data.length > 0 && (
          <span className="text-sm text-[--color-text-muted]">
            Total: <span className="font-mono font-semibold text-[--color-text]">{fmt(totalValue)}</span>
          </span>
        )}
        <Button size="sm" onClick={() => { setEditing(null); setModalOpen(true) }}>
          <Plus size={14} className="mr-1" /> Add Asset
        </Button>
      </div>

      {assetsQ.isLoading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : !assetsQ.data?.length ? (
        <EmptyState
          icon={<Coins size={32} />}
          title="No manual assets yet"
          description="Add your gold, FDs, PPF, NPS, bonds, and other assets to build a complete net-worth picture."
          action={
            <Button size="sm" onClick={() => { setEditing(null); setModalOpen(true) }}>
              <Plus size={14} className="mr-1" /> Add First Asset
            </Button>
          }
        />
      ) : (
        <div className="border border-[--color-border] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[--color-border] text-[--color-text-muted] bg-[--color-surface-2]">
                <th className="text-left px-4 py-2 text-xs font-medium">Type</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Name / Institution</th>
                <th className="text-right px-4 py-2 text-xs font-medium">Current Value</th>
                <th className="text-right px-4 py-2 text-xs font-medium">Gain / Loss</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Purchase</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Maturity</th>
                <th className="px-4 py-2 w-20" />
              </tr>
            </thead>
            <tbody>
              {assetsQ.data.map((asset) => (
                <AssetRow
                  key={asset.id}
                  asset={asset}
                  onEdit={() => { setEditing(asset); setModalOpen(true) }}
                  onDeleted={() => void assetsQ.refetch()}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modalOpen && (
        <AssetFormModal
          editing={editing}
          onClose={closeModal}
          onSaved={onSaved}
        />
      )}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export function PortfolioPage() {
  const qc = useQueryClient()
  const nwQ = useQuery({ queryKey: ['net-worth'], queryFn: getNetWorth })

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <Tabs defaultValue="networth">
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="networth">
              <Wallet size={14} className="mr-1.5 inline" /> Net Worth
            </TabsTrigger>
            <TabsTrigger value="mf">
              <PiggyBank size={14} className="mr-1.5 inline" /> Mutual Funds
            </TabsTrigger>
            <TabsTrigger value="manual">
              <Coins size={14} className="mr-1.5 inline" /> Other Assets
            </TabsTrigger>
          </TabsList>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void qc.invalidateQueries({ queryKey: ['net-worth'] })}
            disabled={nwQ.isFetching}
            title="Refresh net worth"
          >
            <RefreshCw size={13} className={nwQ.isFetching ? 'animate-spin' : ''} />
          </Button>
        </div>

        <TabsContent value="networth" className="pt-4">
          {nwQ.isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-32" />
              <Skeleton className="h-4" />
              <div className="grid grid-cols-3 gap-3">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
              </div>
            </div>
          ) : nwQ.data ? (
            <NetWorthCard data={nwQ.data} />
          ) : null}
        </TabsContent>

        <TabsContent value="mf">
          <MutualFundsTab />
        </TabsContent>

        <TabsContent value="manual">
          <ManualAssetsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
