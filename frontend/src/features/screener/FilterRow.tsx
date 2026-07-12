import { Trash2 } from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import type { FilterSpec } from '@/lib/api/stocks'

// Phase 2 available fields (matches backend catalog.py)
const FIELDS: { value: string; label: string; type: 'bool' | 'str' | 'int' | 'decimal' | 'date' }[] = [
  { value: 'is_nifty50',   label: 'Nifty 50',        type: 'bool' },
  { value: 'is_banknifty', label: 'Bank Nifty',       type: 'bool' },
  { value: 'is_finnifty',  label: 'Fin Nifty',        type: 'bool' },
  { value: 'is_fno',       label: 'F&O Stock',        type: 'bool' },
  { value: 'sector',       label: 'Sector',            type: 'str' },
  { value: 'industry',     label: 'Industry',          type: 'str' },
  { value: 'symbol',       label: 'Symbol',            type: 'str' },
  { value: 'exchange',     label: 'Exchange',          type: 'str' },
  { value: 'lot_size',     label: 'Lot Size',          type: 'int' },
  { value: 'listed_on',    label: 'Listed On',         type: 'date' },
]

const OPS_BY_TYPE: Record<string, { value: string; label: string }[]> = {
  bool:    [{ value: 'eq', label: 'is' }],
  str:     [
    { value: 'eq',   label: '=' },
    { value: 'neq',  label: '≠' },
    { value: 'like', label: 'contains' },
    { value: 'in',   label: 'is one of' },
  ],
  int:     [
    { value: 'eq',      label: '=' },
    { value: 'gt',      label: '>' },
    { value: 'gte',     label: '≥' },
    { value: 'lt',      label: '<' },
    { value: 'lte',     label: '≤' },
    { value: 'between', label: 'between' },
  ],
  decimal: [
    { value: 'eq',      label: '=' },
    { value: 'gt',      label: '>' },
    { value: 'gte',     label: '≥' },
    { value: 'lt',      label: '<' },
    { value: 'lte',     label: '≤' },
    { value: 'between', label: 'between' },
  ],
  date:    [
    { value: 'gt',      label: 'after' },
    { value: 'gte',     label: 'on or after' },
    { value: 'lt',      label: 'before' },
    { value: 'lte',     label: 'on or before' },
    { value: 'between', label: 'between' },
  ],
}

function defaultValueForField(fieldType: string, op: string): unknown {
  if (fieldType === 'bool') return true
  if (op === 'between') return ['', '']
  if (op === 'in') return ''
  return ''
}

interface Props {
  filter: FilterSpec
  onChange: (patch: Partial<FilterSpec>) => void
  onRemove: () => void
}

export function FilterRow({ filter, onChange, onRemove }: Props) {
  const fieldDef = FIELDS.find(f => f.value === filter.field) ?? FIELDS[0]
  const ops = OPS_BY_TYPE[fieldDef.type] ?? []

  function handleFieldChange(newField: string | null) {
    if (!newField) return
    const newDef = FIELDS.find(f => f.value === newField)!
    const newOps = OPS_BY_TYPE[newDef.type] ?? []
    const newOp = newOps[0]?.value ?? 'eq'
    onChange({ field: newField, op: newOp, value: defaultValueForField(newDef.type, newOp) })
  }

  function handleOpChange(newOp: string | null) {
    if (!newOp) return
    onChange({ op: newOp, value: defaultValueForField(fieldDef.type, newOp) })
  }

  function renderValueInput() {
    if (fieldDef.type === 'bool') {
      return (
        <Select
          value={String(filter.value)}
          onValueChange={v => { if (v) onChange({ value: v === 'true' }) }}
        >
          <SelectTrigger className="w-28 bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus:ring-(--color-accent)">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-(--color-surface-3) border-(--color-border) text-(--color-text)">
            <SelectItem value="true">Yes</SelectItem>
            <SelectItem value="false">No</SelectItem>
          </SelectContent>
        </Select>
      )
    }

    if (filter.op === 'between') {
      const vals = Array.isArray(filter.value) ? filter.value as string[] : ['', '']
      return (
        <div className="flex items-center gap-1">
          <Input
            className="w-24 bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus-visible:ring-(--color-accent)"
            placeholder="from"
            value={vals[0] ?? ''}
            onChange={e => onChange({ value: [e.target.value, vals[1] ?? ''] })}
          />
          <span className="text-(--color-text-muted) text-xs">–</span>
          <Input
            className="w-24 bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus-visible:ring-(--color-accent)"
            placeholder="to"
            value={vals[1] ?? ''}
            onChange={e => onChange({ value: [vals[0] ?? '', e.target.value] })}
          />
        </div>
      )
    }

    if (fieldDef.type === 'date') {
      return (
        <Input
          type="date"
          className="w-40 bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus-visible:ring-(--color-accent)"
          value={String(filter.value ?? '')}
          onChange={e => onChange({ value: e.target.value })}
        />
      )
    }

    return (
      <Input
        className="w-40 bg-(--color-surface-3) border-(--color-border) text-(--color-text) placeholder:text-(--color-text-muted) focus-visible:ring-(--color-accent)"
        placeholder={filter.op === 'in' ? 'A,B,C' : 'value'}
        value={String(filter.value ?? '')}
        onChange={e => {
          // 'in' op: split comma-separated into array for the API
          const raw = e.target.value
          onChange({ value: filter.op === 'in' ? raw : raw })
        }}
      />
    )
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Field selector */}
      <Select value={filter.field} onValueChange={handleFieldChange}>
        <SelectTrigger className="w-40 bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus:ring-(--color-accent)">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-(--color-surface-3) border-(--color-border) text-(--color-text)">
          {FIELDS.map(f => (
            <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Operator selector */}
      <Select value={filter.op} onValueChange={handleOpChange}>
        <SelectTrigger className="w-28 bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus:ring-(--color-accent)">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-(--color-surface-3) border-(--color-border) text-(--color-text)">
          {ops.map(o => (
            <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Value input */}
      {renderValueInput()}

      {/* Remove */}
      <button
        type="button"
        onClick={onRemove}
        className="p-1.5 text-(--color-text-muted) hover:text-(--color-error) transition-colors rounded"
        aria-label="Remove filter"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
