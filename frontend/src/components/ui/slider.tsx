import { cn } from '@/lib/utils'

interface SliderProps {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  label?: string
  className?: string
}

export function Slider({ value, onChange, min = 0, max = 100, step = 1, label, className }: SliderProps) {
  const pct = ((value - min) / (max - min)) * 100

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      {label && (
        <div className="flex justify-between text-xs text-(--color-text-muted)">
          <span>{label}</span>
          <span className="font-mono text-(--color-text)">{value}%</span>
        </div>
      )}
      <div className="relative h-5 flex items-center">
        <div className="w-full h-1.5 rounded-full bg-(--color-surface-3) overflow-hidden">
          <div
            className="h-full rounded-full bg-(--color-accent) transition-all"
            style={{ width: `${pct}%` }}
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
          style={{ touchAction: 'none' }}
        />
        {/* Thumb */}
        <div
          className="absolute w-4 h-4 rounded-full bg-(--color-accent) border-2 border-(--color-surface-2) shadow pointer-events-none"
          style={{ left: `calc(${pct}% - 8px)` }}
        />
      </div>
    </div>
  )
}
