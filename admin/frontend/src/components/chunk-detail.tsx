'use client'
import { useEffect, useState } from 'react'
import { api } from '@/hooks/use-api'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import type { ChunkItem, ChunkQuality } from '@/lib/types'

interface Props {
  chunkId: string
  onSave: () => Promise<void>
  onDelete: () => Promise<void>
}

const QUALITY_BADGE: Record<ChunkQuality, string> = {
  good: 'bg-green-500/15 text-green-400 border-green-500/30',
  warning: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  bad: 'bg-red-500/15 text-red-400 border-red-500/30',
}

export function ChunkDetail({ chunkId, onSave, onDelete }: Props) {
  const { toast } = useToast()
  const [chunk, setChunk] = useState<ChunkItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!chunkId) return
    setLoading(true)
    setError(null)
    setEditing(false)
    api<ChunkItem>(`/api/chunks/${chunkId}`)
      .then((c) => {
        setChunk(c)
        setEditContent(c.content)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [chunkId])

  const handleEdit = () => {
    if (chunk) {
      setEditContent(chunk.content)
      setEditing(true)
    }
  }

  const handleCancel = () => {
    setEditing(false)
    if (chunk) setEditContent(chunk.content)
  }

  const handleSave = async () => {
    if (!chunk) return
    setSaving(true)
    try {
      await api(`/api/chunks/${chunkId}`, {
        method: 'PUT',
        body: JSON.stringify({ content: editContent }),
      })
      setChunk({ ...chunk, content: editContent })
      setEditing(false)
      toast('Chunk saved', 'success')
      await onSave()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Save failed'
      setError(msg)
      toast('Failed to save chunk', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!window.confirm('Delete this chunk? This cannot be undone.')) return
    try {
      await api(`/api/chunks/${chunkId}`, { method: 'DELETE' })
      toast('Chunk deleted', 'success')
      await onDelete()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
      toast('Failed to delete chunk', 'error')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
        Loading…
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-3 py-2 text-xs text-destructive">{error}</div>
    )
  }

  if (!chunk) {
    return (
      <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
        Select a chunk to see details
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 text-sm">
      {/* Chunk ID */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Chunk ID</div>
        <div className="truncate font-mono text-[11px] text-foreground/60" title={chunk.id}>
          {chunk.id}
        </div>
      </div>

      {/* Meta badges row */}
      <div className="flex flex-wrap gap-1.5">
        <span className="rounded border border-border bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
          {chunk.original_type}
        </span>
        <span className="rounded border border-border bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
          p.{chunk.page_idx}
        </span>
        <span className="rounded border border-border bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
          {chunk.tokens} tokens
        </span>
        {chunk.is_multimodal && (
          <span className="rounded border border-border bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
            multimodal
          </span>
        )}
        <span
          className={`rounded border px-2 py-0.5 text-[10px] font-medium ${QUALITY_BADGE[chunk.quality]}`}
        >
          {chunk.quality}
        </span>
      </div>

      {/* Quality reasons */}
      {chunk.quality_reasons && chunk.quality_reasons.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Quality Reasons
          </div>
          <div className="flex flex-wrap gap-1">
            {chunk.quality_reasons.map((r, i) => (
              <span
                key={i}
                className="rounded bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
              >
                {r}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Document */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Document</div>
        <div className="truncate font-mono text-[11px] text-foreground/60" title={chunk.file_path}>
          {chunk.file_path}
        </div>
      </div>

      {/* Content */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Content</div>
        <textarea
          value={editing ? editContent : chunk.content}
          onChange={editing ? (e) => setEditContent(e.target.value) : undefined}
          readOnly={!editing}
          rows={10}
          className={`w-full resize-y rounded border border-border bg-background px-3 py-2 font-mono text-xs leading-relaxed text-foreground focus:outline-none ${
            editing ? 'focus:ring-1 focus:ring-ring' : 'cursor-default opacity-80'
          }`}
        />
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        {!editing ? (
          <>
            <Button size="xs" variant="outline" onClick={handleEdit}>
              Edit
            </Button>
            <Button size="xs" variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </>
        ) : (
          <>
            <Button size="xs" variant="default" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
            <Button size="xs" variant="outline" onClick={handleCancel} disabled={saving}>
              Cancel
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
