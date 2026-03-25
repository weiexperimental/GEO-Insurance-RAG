'use client'
import { Button } from '@/components/ui/button'
import type { GraphEdge } from '@/lib/types'

// ─── props ────────────────────────────────────────────────────────────────────

interface Props {
  edge: GraphEdge | null
  onDelete: (edge: GraphEdge) => void
}

// ─── component ────────────────────────────────────────────────────────────────

export function EdgeDetail({ edge, onDelete }: Props) {
  if (!edge) return null

  const descBlocks = edge.description
    ? edge.description.split('<SEP>').map((s) => s.trim()).filter(Boolean)
    : []

  const keywordList = edge.keywords
    ? edge.keywords.split(',').map((k) => k.trim()).filter(Boolean)
    : []

  return (
    <div className="space-y-4 text-sm">
      {/* Header */}
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Relationship</div>

      {/* Source → Target */}
      <div className="flex items-center gap-1.5 text-xs font-medium">
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono truncate max-w-[100px]" title={edge.source}>
          {edge.source}
        </span>
        <span className="text-muted-foreground">→</span>
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono truncate max-w-[100px]" title={edge.target}>
          {edge.target}
        </span>
      </div>

      {/* Keywords */}
      {keywordList.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Keywords</div>
          <div className="flex flex-wrap gap-1">
            {keywordList.map((kw, i) => (
              <span
                key={i}
                className="inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] text-foreground/80"
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Weight */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Weight</div>
        <div className="font-mono text-xs">{edge.weight}</div>
      </div>

      {/* Description blocks */}
      {descBlocks.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Description</div>
          <div className="space-y-2">
            {descBlocks.map((block, i) => (
              <p
                key={i}
                className="rounded bg-muted/50 px-2 py-1.5 text-xs leading-relaxed text-foreground/80"
              >
                {block}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="border-t border-border pt-2">
        <Button size="xs" variant="destructive" onClick={() => onDelete(edge)}>
          Delete
        </Button>
      </div>
    </div>
  )
}
