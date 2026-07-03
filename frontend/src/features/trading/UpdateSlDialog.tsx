import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useMutation } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi, type PositionOut } from '@/lib/api/trading'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/useToast'

interface Props {
  position: PositionOut
  onClose: () => void
  onUpdated: () => void
}

export function UpdateSlDialog({ position, onClose, onUpdated }: Props) {
  const { accessToken } = useAuth()
  const toast = useToast()
  const [newSl, setNewSl] = useState(position.current_sl ?? '')

  const mutation = useMutation({
    mutationFn: (sl: string) => tradingApi.updateSl(position.id, sl, accessToken!),
    onSuccess: () => {
      toast.success('Stop-loss updated')
      onUpdated()
    },
    onError: (err: Error) => toast.error(err.message ?? 'Failed to update SL'),
  })

  const hint = position.side === 'LONG'
    ? `Must be below entry ₹${parseFloat(position.avg_entry_price).toLocaleString('en-IN')}`
    : `Must be above entry ₹${parseFloat(position.avg_entry_price).toLocaleString('en-IN')}`

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.6)' }}
      onClick={onClose}
    >
      <div
        className="bg-[--color-surface-2] border border-[--color-border] rounded-lg p-6 w-full max-w-sm shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-[--color-text] mb-1">Update Stop-Loss</h2>
        <p className="text-xs text-[--color-text-muted] mb-4">
          {position.symbol} {position.side} · {hint}
        </p>

        <label className="block text-xs text-[--color-text-muted] mb-1">New Stop-Loss Price</label>
        <input
          type="number"
          step="0.01"
          value={newSl}
          onChange={(e) => setNewSl(e.target.value)}
          className="w-full bg-[--color-surface-3] border border-[--color-border] rounded px-3 py-2 text-sm text-[--color-text] font-mono focus:outline-none focus:border-[--color-accent] mb-4"
        />

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate(newSl)}
            disabled={!newSl || mutation.isPending}
          >
            {mutation.isPending ? 'Saving…' : 'Update SL'}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
