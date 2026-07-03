import { cn } from '@/lib/utils'

interface DateRange {
  from: string // YYYY-MM-DD
  to: string   // YYYY-MM-DD
}

interface DateRangePickerProps {
  value: DateRange
  onChange: (range: DateRange) => void
  label?: string
  className?: string
  maxDate?: string
}

export function DateRangePicker({ value, onChange, label, className, maxDate }: DateRangePickerProps) {
  const inputStyle =
    'bg-[--color-surface-3] border border-[--color-border] rounded-md px-2.5 py-1.5 text-xs text-[--color-text] focus:outline-none focus:border-[--color-accent] transition-colors'

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      {label && <span className="text-xs text-[--color-text-muted]">{label}</span>}
      <div className="flex items-center gap-2">
        <input
          type="date"
          value={value.from}
          max={value.to || maxDate}
          onChange={(e) => onChange({ ...value, from: e.target.value })}
          className={inputStyle}
        />
        <span className="text-xs text-[--color-text-muted]">–</span>
        <input
          type="date"
          value={value.to}
          min={value.from}
          max={maxDate}
          onChange={(e) => onChange({ ...value, to: e.target.value })}
          className={inputStyle}
        />
      </div>
    </div>
  )
}
