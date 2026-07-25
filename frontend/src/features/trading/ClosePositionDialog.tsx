import { useState } from 'react'
import type { PositionOut } from '@/lib/api/trading'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog'
import { formatInt } from '@/lib/format'

interface Props {
  position: PositionOut
  isLoading: boolean
  onConfirm: (exitPrice?: string) => void
  onClose: () => void
}

export function ClosePositionDialog({ position, isLoading, onConfirm, onClose }: Props) {
  const [exitPrice, setExitPrice] = useState('')

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Close Position</DialogTitle>
          <DialogDescription>
            Close <span className="font-mono font-bold text-(--color-accent)">{position.symbol}</span>{' '}
            {position.side} × {formatInt(position.quantity)}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-1.5">
          <Label htmlFor="exit-price">Exit price (leave blank to use current market price)</Label>
          <Input
            id="exit-price"
            type="number"
            step="0.01"
            value={exitPrice}
            onChange={(e) => setExitPrice(e.target.value)}
            placeholder="e.g. 520.00"
            className="font-mono"
          />
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>Cancel</Button>
          <Button
            variant="destructive"
            onClick={() => onConfirm(exitPrice || undefined)}
            disabled={isLoading}
          >
            {isLoading ? 'Closing…' : 'Close Position'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
