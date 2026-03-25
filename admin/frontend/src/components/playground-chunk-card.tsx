'use client'
import { useCallback } from 'react'
import type { PlaygroundChunk, ChunkRating } from '@/lib/types'

interface Props {
  chunk: PlaygroundChunk
  index: number
  rating: ChunkRating
  highlighted: boolean
  onRate: (chunkId: string, rating: ChunkRating) => void
  onHoverRef: (refId: string | null) => void
}

const RATING_BUTTONS: { value: ChunkRating; label: string; activeClass: string }[] = [
  { value: 'relevant', label: '✓', activeClass: 'bg-green-600 text-white' },
  { value: 'partial', label: '~', activeClass: 'bg-yellow-600 text-white' },
  { value: 'irrelevant', label: '✗', activeClass: 'bg-red-600 text-white' },
]

export function PlaygroundChunkCard({ chunk, index, rating, highlighted, onRate, onHoverRef }: Props) {
  const handleRate = useCallback(
    (value: ChunkRating) => {
      onRate(chunk.chunk_id, rating === value ? null : value)
    },
    [chunk.chunk_id, rating, onRate],
  )

  const fileName = chunk.file_path?.split('/').pop() || 'unknown'

  return (
    <div
      className={`rounded border p-3 text-xs ${highlighted ? 'border-indigo-500 bg-indigo-900/20' : 'border-border bg-background'}`}
      onMouseEnter={() => chunk.reference_id && onHoverRef(chunk.reference_id)}
      onMouseLeave={() => onHoverRef(null)}
    >
      <div className="mb-1 flex items-center justify-between text-[10px] text-muted-foreground">
        <span>#{index + 1} — {fileName}</span>
        {chunk.reference_id && <span className="font-mono">[{chunk.reference_id}]</span>}
      </div>
      <p className="mb-2 max-h-32 overflow-y-auto whitespace-pre-wrap text-foreground leading-relaxed">
        {chunk.content}
      </p>
      <div className="flex gap-1">
        {RATING_BUTTONS.map(({ value, label, activeClass }) => (
          <button
            key={value}
            onClick={() => handleRate(value)}
            className={`rounded px-2 py-0.5 text-[10px] border ${
              rating === value ? activeClass : 'border-border text-muted-foreground hover:text-foreground'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
