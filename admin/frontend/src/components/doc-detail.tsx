'use client'
import { useEffect, useState } from 'react'
import { api } from '@/hooks/use-api'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import type { Document } from '@/lib/types'

interface DocumentDetail extends Document {
  chunk_count: number
  chunk_types: Record<string, number>
  entity_count: number
}

interface Props {
  docId: string
  onDelete: () => Promise<void>
}

const statusBadge: Record<string, string> = {
  processed: 'bg-[hsl(var(--success))]/20 text-[hsl(var(--success))]',
  failed: 'bg-[hsl(var(--error))]/20 text-[hsl(var(--error))]',
  pending: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
  processing: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
  preprocessed: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
}

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '—'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function DocDetail({ docId, onDelete }: Props) {
  const { toast } = useToast()
  const [doc, setDoc] = useState<DocumentDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!docId) return
    setLoading(true)
    setError(null)
    api<DocumentDetail>(`/api/documents/${docId}/detail`)
      .then(setDoc)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [docId])

  const handleDelete = async () => {
    if (!doc) return
    if (!window.confirm(`Delete "${doc.file_name}"? This will remove all chunks, entities, and relationships. This cannot be undone.`)) return
    setDeleting(true)
    try {
      await api(`/api/documents/${docId}`, { method: 'DELETE' })
      toast(`Deleted ${doc.file_name}`, 'success')
      await onDelete()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Delete failed'
      setError(msg)
      toast('Failed to delete document', 'error')
    } finally {
      setDeleting(false)
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
    return <div className="px-3 py-2 text-xs text-destructive">{error}</div>
  }

  if (!doc) {
    return (
      <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
        Select a document to see details
      </div>
    )
  }

  const isHealthy = doc.chunk_count > 0

  return (
    <div className="flex flex-col gap-4 text-sm">
      {/* File name */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">File</div>
        <div className="break-all font-mono text-[11px] text-foreground/80">{doc.file_name}</div>
      </div>

      {/* Status + Health */}
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-1.5 py-0.5 text-[10px] ${statusBadge[doc.status] || 'bg-muted text-muted-foreground'}`}>
          {doc.status}
        </span>
        <span className={`flex items-center gap-1 text-[10px] ${isHealthy ? 'text-green-400' : 'text-red-400'}`}>
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${isHealthy ? 'bg-green-400' : 'bg-red-400'}`} />
          {isHealthy ? 'healthy' : 'no chunks'}
        </span>
      </div>

      {/* Metadata */}
      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Metadata</div>
        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          <span className="text-muted-foreground">Company</span>
          <span>{doc.metadata?.company || '—'}</span>
          <span className="text-muted-foreground">Product</span>
          <span>{doc.metadata?.product_name || '—'}</span>
          <span className="text-muted-foreground">Type</span>
          <span>{doc.metadata?.product_type || '—'}</span>
          <span className="text-muted-foreground">Doc Type</span>
          <span>{doc.metadata?.document_type || '—'}</span>
          <span className="text-muted-foreground">Date</span>
          <span>{doc.metadata?.document_date || '—'}</span>
          <span className="text-muted-foreground">Updated</span>
          <span>{timeAgo(doc.updated_at)}</span>
        </div>
      </div>

      {/* Chunk stats */}
      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Chunks</div>
        <div className="text-xs">
          <span className="font-semibold text-foreground">{doc.chunk_count}</span>
          <span className="ml-1 text-muted-foreground">total</span>
        </div>
        {Object.keys(doc.chunk_types).length > 0 && (
          <div className="flex flex-wrap gap-1">
            {Object.entries(doc.chunk_types).map(([type, count]) => (
              <span key={type} className="rounded border border-border bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                {type}: {count}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Entity count */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Entities</div>
        <div className="text-xs">
          <span className="font-semibold text-foreground">{doc.entity_count}</span>
          <span className="ml-1 text-muted-foreground">graph nodes</span>
        </div>
      </div>

      {/* Document ID */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Document ID</div>
        <div className="truncate font-mono text-[10px] text-foreground/40" title={doc.document_id}>
          {doc.document_id}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        <Button size="xs" variant="destructive" onClick={handleDelete} disabled={deleting}>
          {deleting ? 'Deleting…' : 'Delete'}
        </Button>
      </div>
    </div>
  )
}
