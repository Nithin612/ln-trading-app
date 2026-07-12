/**
 * Thin wrapper around the base-ui Select primitives.
 * Accepts a flat `options` array and `onChange` callback.
 * Use this anywhere a simple dropdown is needed.
 *
 * Empty string values are supported — they are mapped to the internal sentinel
 * '__empty__' and back transparently, so callers never see the sentinel.
 */

import { cn } from '@/lib/utils'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select'

export interface SelectOption {
  value: string
  label: string
}

interface SimpleSelectProps {
  value: string
  onChange: (v: string) => void
  options: SelectOption[]
  placeholder?: string
  className?: string
  disabled?: boolean
  size?: 'sm' | 'default'
}

const EMPTY = '__empty__'

export function SimpleSelect({
  value,
  onChange,
  options,
  placeholder = 'Select…',
  className,
  disabled,
  size = 'default',
}: SimpleSelectProps) {
  const selectValue = value === '' ? EMPTY : value || undefined

  return (
    <Select
      value={selectValue}
      onValueChange={(v) => onChange(v === EMPTY ? '' : (v ?? ''))}
      disabled={disabled}
    >
      <SelectTrigger size={size} className={cn('min-w-[110px]', className)}>
        {/* base-ui's Value renders the raw VALUE by default — invisible
            while every caller had value≡label (sectors, segments), wrong
            once watchlists select by id ("4" instead of "Momo"), and the
            EMPTY sentinel leaked as "__empty__" when no ''-option exists.
            Resolve the label explicitly; fall back to the placeholder. */}
        <SelectValue placeholder={placeholder}>
          {selectValue === undefined
            ? undefined
            : (options.find((o) => (o.value === '' ? EMPTY : o.value) === selectValue)
                ?.label ?? (selectValue === EMPTY ? placeholder : selectValue))}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt.value === '' ? EMPTY : opt.value} value={opt.value === '' ? EMPTY : opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
