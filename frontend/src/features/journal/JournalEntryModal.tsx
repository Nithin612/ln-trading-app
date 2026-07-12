import { useState, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  journalApi,
  EMOTIONS_BEFORE,
  EMOTIONS_AFTER,
  type JournalEntry,
  type JournalEntryCreate,
  type JournalEntryUpdate,
} from '@/lib/api/journal'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { SimpleSelect } from '@/components/ui/simple-select'
import { useToast } from '@/hooks/useToast'
import { cn } from '@/lib/utils'

interface Props {
  entry?: JournalEntry
  open: boolean
  onClose: () => void
}

const TODAY = new Date().toISOString().split('T')[0]

export function JournalEntryModal({ entry, open, onClose }: Props) {
  const qc = useQueryClient()
  const { success, error } = useToast()
  const fileRef = useRef<HTMLInputElement>(null)

  const isEdit = !!entry

  const [form, setForm] = useState<JournalEntryCreate & { realized_pnl: string }>(() => ({
    trade_date: entry?.trade_date ?? TODAY,
    side: entry?.side ?? null,
    entry_price: entry?.entry_price ?? null,
    exit_price: entry?.exit_price ?? null,
    quantity: entry?.quantity ?? null,
    realized_pnl: entry?.realized_pnl ?? '',
    notes: entry?.notes ?? null,
    lesson: entry?.lesson ?? null,
    emotion_before: entry?.emotion_before ?? null,
    emotion_after: entry?.emotion_after ?? null,
    tags: entry?.tags ?? [],
    stock_id: entry?.stock_id ?? null,
  }))

  const [tagInput, setTagInput] = useState('')
  const [uploading, setUploading] = useState(false)

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const createMut = useMutation({
    mutationFn: (data: JournalEntryCreate) => journalApi.create(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['journal'] })
      void qc.invalidateQueries({ queryKey: ['journal-emotions'] })
      success('Entry created')
      onClose()
    },
    onError: (e: Error) => error(e.message),
  })

  const updateMut = useMutation({
    mutationFn: (data: JournalEntryUpdate) => journalApi.update(entry!.id, data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['journal'] })
      void qc.invalidateQueries({ queryKey: ['journal-emotions'] })
      success('Entry updated')
      onClose()
    },
    onError: (e: Error) => error(e.message),
  })

  const uploadMut = useMutation({
    mutationFn: (file: File) => journalApi.uploadScreenshot(entry!.id, file),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['journal'] })
      success('Screenshot uploaded')
    },
    onError: (e: Error) => error(e.message),
  })

  const deleteScreenshotMut = useMutation({
    mutationFn: (filename: string) => journalApi.deleteScreenshot(entry!.id, filename),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['journal'] }),
    onError: (e: Error) => error(e.message),
  })

  const handleSubmit = () => {
    const payload = {
      trade_date: form.trade_date,
      side: form.side ?? undefined,
      entry_price: form.entry_price || undefined,
      exit_price: form.exit_price || undefined,
      quantity: form.quantity ?? undefined,
      realized_pnl: form.realized_pnl || undefined,
      notes: form.notes || undefined,
      lesson: form.lesson || undefined,
      emotion_before: form.emotion_before ?? undefined,
      emotion_after: form.emotion_after ?? undefined,
      tags: form.tags ?? [],
      stock_id: form.stock_id ?? undefined,
    }
    if (isEdit) {
      updateMut.mutate(payload)
    } else {
      createMut.mutate(payload)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !entry) return
    setUploading(true)
    try {
      await uploadMut.mutateAsync(file)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const tags = form.tags ?? []

  const addTag = () => {
    const t = tagInput.trim()
    if (t && !tags.includes(t)) {
      set('tags', [...tags, t])
    }
    setTagInput('')
  }

  const removeTag = (tag: string) => set('tags', tags.filter((t) => t !== tag))

  const busy = createMut.isPending || updateMut.isPending

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="max-w-lg w-full" showCloseButton>
        <h2 className="text-base font-semibold text-(--color-text) mb-4">
          {isEdit ? 'Edit Journal Entry' : 'New Journal Entry'}
        </h2>

        <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">

          {/* Date + Side */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="trade_date">Trade Date</Label>
              <Input
                id="trade_date"
                type="date"
                value={form.trade_date}
                onChange={(e) => set('trade_date', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="side">Side</Label>
              <SimpleSelect
                value={form.side ?? ''}
                onChange={(v) => set('side', (v || null) as 'LONG' | 'SHORT' | null)}
                options={[
                  { value: '', label: '— None —' },
                  { value: 'LONG', label: 'Long' },
                  { value: 'SHORT', label: 'Short' },
                ]}
              />
            </div>
          </div>

          {/* Prices + Qty */}
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label htmlFor="entry_price">Entry ₹</Label>
              <Input
                id="entry_price"
                type="number"
                step="0.01"
                placeholder="0.00"
                value={form.entry_price ?? ''}
                onChange={(e) => set('entry_price', e.target.value || null)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="exit_price">Exit ₹</Label>
              <Input
                id="exit_price"
                type="number"
                step="0.01"
                placeholder="0.00"
                value={form.exit_price ?? ''}
                onChange={(e) => set('exit_price', e.target.value || null)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="quantity">Qty</Label>
              <Input
                id="quantity"
                type="number"
                step="1"
                placeholder="0"
                value={form.quantity ?? ''}
                onChange={(e) =>
                  set('quantity', e.target.value ? Number(e.target.value) : null)
                }
              />
            </div>
          </div>

          {/* P&L */}
          <div className="space-y-1">
            <Label htmlFor="realized_pnl">Realized P&L (₹)</Label>
            <Input
              id="realized_pnl"
              type="number"
              step="0.01"
              placeholder="e.g. 2000 or -800"
              value={form.realized_pnl ?? ''}
              onChange={(e) => set('realized_pnl', e.target.value)}
            />
          </div>

          {/* Emotions */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="emotion_before">Emotion Before</Label>
              <SimpleSelect
                value={form.emotion_before ?? ''}
                onChange={(v) => set('emotion_before', (v || null) as typeof form.emotion_before)}
                options={[
                  { value: '', label: '— None —' },
                  ...EMOTIONS_BEFORE.map((e) => ({
                    value: e,
                    label: e.charAt(0).toUpperCase() + e.slice(1),
                  })),
                ]}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="emotion_after">Emotion After</Label>
              <SimpleSelect
                value={form.emotion_after ?? ''}
                onChange={(v) => set('emotion_after', (v || null) as typeof form.emotion_after)}
                options={[
                  { value: '', label: '— None —' },
                  ...EMOTIONS_AFTER.map((e) => ({
                    value: e,
                    label: e.charAt(0).toUpperCase() + e.slice(1),
                  })),
                ]}
              />
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-1">
            <Label htmlFor="notes">Notes</Label>
            <textarea
              id="notes"
              rows={3}
              placeholder="What happened? Why did you take this trade?"
              className={cn(
                'w-full resize-y rounded-md border border-(--color-border) px-3 py-2 text-sm',
                'bg-(--color-surface) text-(--color-text) placeholder:text-(--color-text-muted)',
                'focus:outline-none focus:ring-1 focus:ring-(--color-accent)',
              )}
              value={form.notes ?? ''}
              onChange={(e) => set('notes', e.target.value || null)}
            />
          </div>

          {/* Lesson */}
          <div className="space-y-1">
            <Label htmlFor="lesson">Lesson Learned</Label>
            <textarea
              id="lesson"
              rows={2}
              placeholder="What would you do differently next time?"
              className={cn(
                'w-full resize-y rounded-md border border-(--color-border) px-3 py-2 text-sm',
                'bg-(--color-surface) text-(--color-text) placeholder:text-(--color-text-muted)',
                'focus:outline-none focus:ring-1 focus:ring-(--color-accent)',
              )}
              value={form.lesson ?? ''}
              onChange={(e) => set('lesson', e.target.value || null)}
            />
          </div>

          {/* Tags */}
          <div className="space-y-1">
            <Label>Tags</Label>
            <div className="flex gap-2">
              <Input
                placeholder="Add tag…"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag() } }}
              />
              <Button variant="outline" size="sm" onClick={addTag} type="button">
                Add
              </Button>
            </div>
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {tags.map((t) => (
                  <span
                    key={t}
                    className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs border border-(--color-border) text-(--color-text-muted)"
                  >
                    {t}
                    <button
                      type="button"
                      onClick={() => removeTag(t)}
                      className="hover:text-(--color-bear) leading-none"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Screenshots — only available when editing an existing entry */}
          {isEdit && (
            <div className="space-y-2">
              <Label>Screenshots</Label>
              {entry.screenshot_paths.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {entry.screenshot_paths.map((path) => {
                    const filename = path.split('/').pop()!
                    return (
                      <div key={path} className="relative group">
                        <img
                          src={path}
                          alt="trade screenshot"
                          className="w-24 h-16 object-cover rounded border border-(--color-border)"
                        />
                        <button
                          type="button"
                          onClick={() => deleteScreenshotMut.mutate(filename)}
                          className={cn(
                            'absolute top-0.5 right-0.5 w-4 h-4 rounded-full text-[8px] font-bold',
                            'bg-(--color-bear) text-white opacity-0 group-hover:opacity-100 transition-opacity',
                            'flex items-center justify-center',
                          )}
                        >
                          ×
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
              <div>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="hidden"
                  onChange={(e) => void handleFileChange(e)}
                />
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  disabled={uploading}
                  onClick={() => fileRef.current?.click()}
                >
                  {uploading ? 'Uploading…' : '+ Add Screenshot'}
                </Button>
                <p className="text-xs text-(--color-text-muted) mt-1">
                  Max 5 MB — JPEG, PNG, WebP, GIF
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 pt-4 border-t border-(--color-border) mt-4">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={busy || !form.trade_date}>
            {busy ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Entry'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
