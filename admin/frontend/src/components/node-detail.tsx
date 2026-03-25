'use client'
import { useEffect, useState } from 'react'
import { api } from '@/hooks/use-api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { GraphNode, EntityDetail, SimilarEntity } from '@/lib/types'

// ─── type color map ────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  organization: '#4ade80',
  concept: '#60a5fa',
  product: '#a78bfa',
  person: '#f472b6',
  location: '#fbbf24',
  event: '#fb923c',
  method: '#2dd4bf',
}

// ─── props ────────────────────────────────────────────────────────────────────

interface Props {
  node: GraphNode | null
  onEdit: (node: GraphNode) => void
  onDelete: (node: GraphNode) => void
  onMerge: (node: GraphNode) => void
  onNavigate: (entityId: string) => void
}

// ─── component ────────────────────────────────────────────────────────────────

export function NodeDetail({ node, onEdit, onDelete, onMerge, onNavigate }: Props) {
  const [detail, setDetail] = useState<EntityDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [similar, setSimilar] = useState<SimilarEntity[]>([])
  const [similarLoading, setSimilarLoading] = useState(false)

  useEffect(() => {
    if (!node) {
      setDetail(null)
      setSimilar([])
      return
    }
    setLoading(true)
    setError(null)
    api<EntityDetail>(`/api/graph/entity/${encodeURIComponent(node.id)}`)
      .then((d) => setDetail(d))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))

    setSimilarLoading(true)
    api<SimilarEntity[]>(`/api/graph/similar/${encodeURIComponent(node.id)}`)
      .then((d) => setSimilar(d))
      .catch(() => setSimilar([]))
      .finally(() => setSimilarLoading(false))
  }, [node])

  if (!node) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
        Click a node to see details
      </div>
    )
  }

  const typeColor = TYPE_COLORS[node.entity_type] ?? '#666666'

  return (
    <div className="space-y-4 text-sm">
      {/* Header */}
      <div className="space-y-2">
        <div className="text-base font-semibold leading-tight break-all">{node.id}</div>
        <span
          className="inline-flex h-5 items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
          style={{ backgroundColor: `${typeColor}22`, color: typeColor, border: `1px solid ${typeColor}55` }}
        >
          {node.entity_type}
        </span>
      </div>

      {/* Description */}
      {node.description && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Description</div>
          <p className="text-xs leading-relaxed text-foreground/80">{node.description}</p>
        </div>
      )}

      {/* Source document */}
      {node.file_path && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Source</div>
          <div className="truncate font-mono text-[11px] text-foreground/60">{node.file_path}</div>
        </div>
      )}

      {/* Connections */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Connections
          {detail && ` (${detail.connections.length})`}
        </div>
        {loading && <div className="text-xs text-muted-foreground">Loading…</div>}
        {error && <div className="text-xs text-destructive">{error}</div>}
        {!loading && !error && detail && detail.connections.length === 0 && (
          <div className="text-xs text-muted-foreground">No connections</div>
        )}
        {!loading && detail && detail.connections.length > 0 && (
          <ul className="space-y-1">
            {detail.connections.map((c, i) => (
              <li key={i}>
                <button
                  onClick={() => onNavigate(c.other_entity)}
                  className="flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-xs hover:bg-muted transition-colors"
                >
                  <span
                    className="shrink-0 text-[9px] font-mono text-muted-foreground"
                    title={c.direction}
                  >
                    {c.direction === 'outgoing' ? '→' : '←'}
                  </span>
                  <span className="truncate font-medium">{c.other_entity}</span>
                  {c.keywords && (
                    <span className="ml-auto shrink-0 truncate text-[10px] text-muted-foreground max-w-[80px]">
                      {c.keywords}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Similar Entities */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Similar Entities
          {similar.length > 0 && ` (${similar.length})`}
        </div>
        {similarLoading && <div className="text-xs text-muted-foreground">Loading…</div>}
        {!similarLoading && similar.length === 0 && (
          <div className="text-xs text-muted-foreground">No similar entities found</div>
        )}
        {!similarLoading && similar.length > 0 && (
          <ul className="space-y-2">
            {similar.map((s, i) => (
              <li key={s.entity_id} className="rounded border border-border px-2 py-1.5 space-y-1">
                <div className="flex items-start justify-between gap-1">
                  <span className="text-xs font-medium leading-tight break-all">{s.entity_name}</span>
                  <Button
                    size="xs"
                    variant="outline"
                    className="shrink-0"
                    onClick={() => onMerge({ id: s.entity_id, entity_type: '', description: s.description, file_path: s.file_path, source_ids: [] })}
                  >
                    Merge →
                  </Button>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="inline-flex items-center rounded px-1 py-0.5 text-[9px] font-mono bg-muted text-muted-foreground">
                    vec {s.vector_similarity.toFixed(2)}
                  </span>
                  <span className="inline-flex items-center rounded px-1 py-0.5 text-[9px] font-mono bg-muted text-muted-foreground">
                    name {s.name_similarity.toFixed(2)}
                  </span>
                  {s.reason && (
                    <span className="text-[10px] text-muted-foreground italic truncate max-w-full">{s.reason}</span>
                  )}
                </div>
                {s.description && (
                  <p className="text-[10px] text-foreground/60 leading-snug line-clamp-2">{s.description}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 pt-2 border-t border-border">
        <Button size="xs" variant="outline" onClick={() => onEdit(node)}>
          Edit
        </Button>
        <Button size="xs" variant="outline" onClick={() => onMerge(node)}>
          Merge
        </Button>
        <Button size="xs" variant="destructive" onClick={() => onDelete(node)}>
          Delete
        </Button>
      </div>
    </div>
  )
}
