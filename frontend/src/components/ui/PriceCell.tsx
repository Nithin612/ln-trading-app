import { useEffect, useRef, useState } from "react"
import { cn } from "@/lib/utils"

interface PriceCellProps {
  value: number | undefined
  format?: (n: number) => string
  className?: string
}

export function PriceCell({ value, format, className }: PriceCellProps) {
  const prev = useRef<number | undefined>(undefined)
  const [flash, setFlash] = useState<"up" | "down" | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (prev.current !== undefined && value !== undefined && value !== prev.current) {
      const dir = value > prev.current ? "up" : "down"
      setFlash(dir)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setFlash(null), 250)
    }
    prev.current = value
  }, [value])

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  return (
    <span
      className={cn(
        "tabular-nums transition-colors duration-150",
        flash === "up" && "bg-[--color-profit-bg] text-[--color-profit]",
        flash === "down" && "bg-[--color-loss-bg] text-[--color-loss]",
        className
      )}
    >
      {value !== undefined ? (format ? format(value) : String(value)) : "—"}
    </span>
  )
}
