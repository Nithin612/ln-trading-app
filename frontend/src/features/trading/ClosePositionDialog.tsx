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

        {/*
          V2 — "current market price" is a promise the backend cannot always keep. With no
          live tick `close_position` falls back to the last 1m close, then the last daily
          close, then to `avg_entry_price` itself — which books a FLAT trade at a price the
          market never printed, straight into `realized_pnl` and the paper record.
          Blocking the close would be worse (it is the only way out of the position), so
          the honest move is to say what blank will actually resolve to, HERE, where the
          decision is made.
        */}
        {position.price_state !== 'live' && (
          <div
            id="exit-price-warning"
            role="alert"
            className="rounded border px-3 py-2 text-xs"
            style={{
              background: 'var(--color-warning-bg)',
              borderColor: 'var(--color-warning)',
              color: 'var(--color-warning)',
            }}
          >
            {position.price_state === 'none'
              ? '⚠ No price is available for this name. Leaving the field blank books the '
                + 'exit at your entry price, less slippage and charges — a fabricated fill '
                + 'at a price the market never printed. Enter the price you actually got.'
              : `⚠ There is no live tick for this name. Leaving the field blank uses the `
                + `${position.price_state === 'daily' ? 'previous session close' : 'last 1m close'}`
                + `, not a current price. Enter the price you actually got.`}
          </div>
        )}

        <div className="grid gap-1.5">
          <Label htmlFor="exit-price">
            {position.price_state === 'live'
              ? 'Exit price (leave blank to use current market price)'
              : 'Exit price — recommended'}
          </Label>
          <Input
            id="exit-price"
            type="number"
            step="0.01"
            min="0"
            // F4: the warning explains what a BLANK field resolves to, so it must be
            // announced when focus lands here — not left as a positional "see above".
            aria-describedby={position.price_state !== 'live' ? 'exit-price-warning' : undefined}
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
