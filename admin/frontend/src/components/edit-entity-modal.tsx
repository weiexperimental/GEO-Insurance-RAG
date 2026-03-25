'use client'
import { useState } from 'react'
import { api } from '@/hooks/use-api'
import { Button } from '@/components/ui/button'
import type { GraphNode } from '@/lib/types'

// ─── props ────────────────────────────────────────────────────────────────────

interface Props {
  node: GraphNode
  onSave: () => void
  onCancel: () => void
}

// ─── component ────────────────────────────────────────────────────────────────

export function EditEntityModal({ node, onSave, onCancel }: Props) {
  const [description, setDescription] = useState(node.description ?? '')
  const [entityType, setEntityType] = useState(node.entity_type ?? '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    setLoading(true)
    setError(null)
    try {
      await api(`/api/graph/entity/${encodeURIComponent(node.id)}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: { description, entity_type: entityType } }),
      })
      onSave()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Title */}
        <div className="mb-4 text-sm font-semibold text-foreground">
          Edit Entity —{' '}
          <span className="font-mono text-xs text-muted-foreground">{node.id}</span>
        </div>

        {/* Fields */}
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Entity Type
            </label>
            <input
              type="text"
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30 resize-none"
            />
          </div>
        </div>

        {error && (
          <div className="mt-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="mt-5 flex justify-end gap-2">
          <Button size="xs" variant="outline" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button
            size="xs"
            className="border-blue-500/60 bg-transparent text-blue-400 hover:bg-blue-500/10"
            onClick={handleSave}
            disabled={loading}
          >
            {loading ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    </div>
  )
}
