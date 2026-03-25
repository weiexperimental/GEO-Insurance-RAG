'use client'
import { useState, useCallback } from 'react'
import type { PlaygroundResult, ChunkRating } from '@/lib/types'
import { PlaygroundGraphPath } from './playground-graph-path'
import { PlaygroundChunkCard } from './playground-chunk-card'
import { PlaygroundPromptViewer } from './playground-prompt-viewer'
import { PlaygroundStatsBar } from './playground-stats-bar'

interface Props {
  result: PlaygroundResult
  label?: string
}

const TYPE_COLORS: Record<string, string> = {
  organization: '#4ade80',
  concept: '#60a5fa',
  product: '#a78bfa',
  person: '#f472b6',
  location: '#fbbf24',
  event: '#fb923c',
  method: '#2dd4bf',
}

export function PlaygroundResultPanel({ result, label }: Props) {
  const [ratings, setRatings] = useState<Record<string, ChunkRating>>({})
  const [hoveredRef, setHoveredRef] = useState<string | null>(null)

  const handleRate = useCallback((chunkId: string, rating: ChunkRating) => {
    setRatings((prev) => ({ ...prev, [chunkId]: rating }))
  }, [])

  const { data, metadata, full_prompt, llm_response, timing } = result
  const { keywords, entities, relationships, chunks } = data

  // Parse [N] references in LLM response for highlighting
  const renderResponse = (text: string) => {
    const parts = text.split(/(\[\d+\])/)
    return parts.map((part, i) => {
      const match = part.match(/^\[(\d+)\]$/)
      if (match) {
        const refId = `ref-${match[1]}`
        return (
          <span
            key={i}
            className={`cursor-pointer font-mono text-indigo-400 ${hoveredRef === refId ? 'bg-indigo-900/50 rounded px-0.5' : ''}`}
            onMouseEnter={() => setHoveredRef(refId)}
            onMouseLeave={() => setHoveredRef(null)}
          >
            {part}
          </span>
        )
      }
      return <span key={i}>{part}</span>
    })
  }

  return (
    <div className="space-y-3 overflow-y-auto">
      {label && (
        <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      )}

      {/* Keywords */}
      {(keywords.high_level.length > 0 || keywords.low_level.length > 0) && (
        <div className="text-xs">
          <div className="mb-1 text-[10px] text-muted-foreground">Keywords</div>
          <div className="flex flex-wrap gap-1">
            {keywords.high_level.map((k) => (
              <span key={`h-${k}`} className="rounded bg-indigo-900/40 px-1.5 py-0.5 text-[10px] text-indigo-300">{k}</span>
            ))}
            {keywords.low_level.map((k) => (
              <span key={`l-${k}`} className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">{k}</span>
            ))}
          </div>
        </div>
      )}

      {/* Graph Path */}
      {entities.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] text-muted-foreground">Graph Path</div>
          <PlaygroundGraphPath entities={entities} relationships={relationships} />
        </div>
      )}

      {/* Entities */}
      {entities.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] text-muted-foreground">Entities ({entities.length})</div>
          <div className="space-y-1">
            {entities.map((e) => (
              <div key={e.entity_name} className="flex items-center gap-2 text-xs">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: TYPE_COLORS[e.entity_type] || '#666' }} />
                <span className="text-foreground">{e.entity_name}</span>
                <span className="text-[10px] text-muted-foreground">[{e.entity_type}]</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chunks */}
      {chunks.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] text-muted-foreground">Chunks ({chunks.length})</div>
          <div className="space-y-2">
            {chunks.map((c, i) => (
              <PlaygroundChunkCard
                key={c.chunk_id || i}
                chunk={c}
                index={i}
                rating={ratings[c.chunk_id] ?? null}
                highlighted={hoveredRef === c.reference_id}
                onRate={handleRate}
                onHoverRef={setHoveredRef}
              />
            ))}
          </div>
        </div>
      )}

      {/* Full Prompt */}
      <div>
        <div className="mb-1 text-[10px] text-muted-foreground">Full Prompt</div>
        <PlaygroundPromptViewer prompt={full_prompt} />
      </div>

      {/* LLM Response */}
      {llm_response && (
        <div>
          <div className="mb-1 text-[10px] text-muted-foreground">LLM Response</div>
          <div className="rounded border border-border bg-background p-3 text-xs leading-relaxed text-foreground whitespace-pre-wrap">
            {renderResponse(llm_response)}
          </div>
        </div>
      )}

      {/* Stats */}
      <PlaygroundStatsBar
        timing={timing}
        processingInfo={metadata.processing_info}
      />
    </div>
  )
}
