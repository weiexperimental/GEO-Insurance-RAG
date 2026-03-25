'use client'
import { useState } from 'react'
import { api } from '@/hooks/use-api'
import { Button } from '@/components/ui/button'

// ─── props ────────────────────────────────────────────────────────────────────

interface Props {
  type: 'entity' | 'relation'
  name: string
  source?: string
  target?: string
  onConfirm: () => void
  onCancel: () => void
}

// ─── component ────────────────────────────────────────────────────────────────

export function DeleteConfirmModal({ type, name, source, target, onConfirm, onCancel }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setLoading(true)
    setError(null)
    try {
      if (type === 'entity') {
        await api(`/api/graph/entity/${encodeURIComponent(name)}`, { method: 'DELETE' })
      } else {
        await api('/api/graph/relation', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source, target }),
        })
      }
      onConfirm()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setLoading(false)
    }
  }

  const label =
    type === 'entity'
      ? `Delete entity "${name}"?`
      : `Delete relation "${source}" → "${target}"?`

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Title */}
        <div className="mb-1 text-sm font-semibold text-foreground">Confirm Delete</div>

        {/* Body */}
        <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
          {label}
          <br />
          This action cannot be undone.
        </p>

        {error && <div className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</div>}

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <Button size="xs" variant="outline" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button
            size="xs"
            variant="destructive"
            onClick={handleConfirm}
            disabled={loading}
          >
            {loading ? 'Deleting…' : 'Delete'}
          </Button>
        </div>
      </div>
    </div>
  )
}
