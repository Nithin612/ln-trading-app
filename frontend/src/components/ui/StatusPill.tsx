import { CheckCircle2, XCircle, Circle, Clock, MinusCircle, Ban } from "lucide-react"
import { cn } from "@/lib/utils"

type Status =
  | "active"
  | "expired"
  | "hit_tp"
  | "hit_sl"
  | "pending"
  | "filled"
  | "rejected"
  | "cancelled"
  | "buy"
  | "sell"

const STATUS_MAP: Record<Status, {
  label: string
  icon: React.ElementType
  className: string
}> = {
  active:    { label: "Active",    icon: Circle,       className: "text-[--color-info]    bg-[--color-info]/10    border-[--color-info]/20" },
  pending:   { label: "Pending",   icon: Clock,        className: "text-[--color-warning] bg-[--color-warning]/10 border-[--color-warning]/20" },
  filled:    { label: "Filled",    icon: CheckCircle2, className: "text-[--color-profit]  bg-[--color-profit-bg]  border-[--color-profit]/20" },
  hit_tp:    { label: "Hit TP",    icon: CheckCircle2, className: "text-[--color-profit]  bg-[--color-profit-bg]  border-[--color-profit]/20" },
  hit_sl:    { label: "Hit SL",    icon: XCircle,      className: "text-[--color-loss]    bg-[--color-loss-bg]    border-[--color-loss]/20" },
  rejected:  { label: "Rejected",  icon: XCircle,      className: "text-[--color-loss]    bg-[--color-loss-bg]    border-[--color-loss]/20" },
  expired:   { label: "Expired",   icon: MinusCircle,  className: "text-[--color-text-muted] bg-[--color-surface-3] border-[--color-border]" },
  cancelled: { label: "Cancelled", icon: Ban,          className: "text-[--color-text-muted] bg-[--color-surface-3] border-[--color-border]" },
  buy:       { label: "↑ BUY",     icon: Circle,       className: "text-[--color-profit]  bg-[--color-profit-bg]  border-[--color-profit]/20" },
  sell:      { label: "↓ SELL",    icon: Circle,       className: "text-[--color-loss]    bg-[--color-loss-bg]    border-[--color-loss]/20" },
}

interface StatusPillProps {
  kind: Status
  className?: string
  children?: React.ReactNode
}

export function StatusPill({ kind, className, children }: StatusPillProps) {
  const { label, icon: Icon, className: statusClass } = STATUS_MAP[kind] ?? STATUS_MAP.expired

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md border text-[10px] font-medium",
        statusClass,
        className
      )}
    >
      <Icon className="size-2.5" />
      {children ?? label}
    </span>
  )
}
