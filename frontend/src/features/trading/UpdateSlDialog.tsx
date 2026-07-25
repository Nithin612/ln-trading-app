import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi, type PositionOut } from '@/lib/api/trading'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog'
import { useToast } from '@/hooks/useToast'
import { formatINR } from '@/lib/format'

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
    ? `Must be below entry ₹${formatINR(parseFloat(position.avg_entry_price))}`
    : `Must be above entry ₹${formatINR(parseFloat(position.avg_entry_price))}`

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update Stop-Loss</DialogTitle>
          <DialogDescription>{position.symbol} {position.side} · {hint}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-1.5">
          <Label htmlFor="new-sl">New stop-loss price</Label>
          <Input
            id="new-sl"
            type="number"
            step="0.01"
            value={newSl}
            onChange={(e) => setNewSl(e.target.value)}
            className="font-mono"
          />
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>Cancel</Button>
          <Button onClick={() => mutation.mutate(newSl)} disabled={!newSl || mutation.isPending}>
            {mutation.isPending ? 'Saving…' : 'Update SL'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
