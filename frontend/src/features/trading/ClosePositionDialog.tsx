import { useState } from 'react'
import { createPortal } from 'react-dom'
import type { PositionOut } from '@/lib/api/trading'
import { Button } from '@/components/ui/button'

interface Props {
  position: PositionOut
  isLoading: boolean
  onConfirm: (exitPrice?: string) => void
  onClose: () => void
}

export function ClosePositionDialog({ position, isLoading, onConfirm, onClose }: Props) {
  const [exitPrice, setExitPrice] = useState('')

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.6)' }}
      onClick={onClose}
    >
      <div
        className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-6 w-full max-w-sm shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-(--color-text) mb-1">Close Position</h2>
        <p className="text-sm text-(--color-text-muted) mb-4">
          Close <span className="font-mono font-bold text-(--color-accent)">{position.symbol}</span> {position.side} × {position.quantity.toLocaleString('en-IN')}
        </p>

        <label className="block text-xs text-(--color-text-muted) mb-1">
          Exit Price (leave blank to use current market price)
        </label>
        <input
          type="number"
          step="0.01"
          value={exitPrice}
          onChange={(e) => setExitPrice(e.target.value)}
          placeholder="e.g. 520.00"
          className="w-full bg-(--color-surface-3) border border-(--color-border) rounded px-3 py-2 text-sm text-(--color-text) font-mono focus:outline-none focus:border-(--color-accent) mb-4"
        />

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => onConfirm(exitPrice || undefined)}
            disabled={isLoading}
          >
            {isLoading ? 'Closing…' : 'Close Position'}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
