import type { ChunkItem, ChunkQuality } from '@/lib/types'
import { Button } from '@/components/ui/button'

interface Props {
  chunks: ChunkItem[]
  total: number
  page: number
  size: number
  selectedId: string | null
  checkedIds: Set<string>
  onSelect: (id: string) => void
  onToggle: (id: string) => void
  onToggleAll: (checked: boolean) => void
  onPageChange: (page: number) => void
}

const QUALITY_DOT: Record<ChunkQuality, string> = {
  good: 'bg-green-500',
  warning: 'bg-yellow-500',
  bad: 'bg-red-500',
}

const QUALITY_LABEL: Record<ChunkQuality, string> = {
  good: 'text-green-500',
  warning: 'text-yellow-500',
  bad: 'text-red-500',
}

export function ChunksList({
  chunks,
  total,
  page,
  size,
  selectedId,
  checkedIds,
  onSelect,
  onToggle,
  onToggleAll,
  onPageChange,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / size))
  const allChecked = chunks.length > 0 && chunks.every((c) => checkedIds.has(c.id))
  const someChecked = chunks.some((c) => checkedIds.has(c.id)) && !allChecked

  return (
    <div className="flex flex-col gap-0 overflow-hidden">
      {/* Header row */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <input
          type="checkbox"
          checked={allChecked}
          ref={(el) => {
            if (el) el.indeterminate = someChecked
          }}
          onChange={(e) => onToggleAll(e.target.checked)}
          className="size-3.5 accent-indigo-500"
        />
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {total} chunk{total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Chunk rows */}
      <div className="flex-1 overflow-y-auto">
        {chunks.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
            No chunks found
          </div>
        ) : (
          chunks.map((chunk, idx) => {
            const isSelected = selectedId === chunk.id
            const isChecked = checkedIds.has(chunk.id)
            const globalIdx = (page - 1) * size + idx + 1
            return (
              <div
                key={chunk.id}
                onClick={() => onSelect(chunk.id)}
                className={`flex cursor-pointer gap-2 border-b border-border px-3 py-2 transition-colors hover:bg-muted/40 ${
                  isSelected ? 'border-l-2 border-l-indigo-500 bg-muted/60' : ''
                }`}
              >
                {/* Checkbox */}
                <div
                  className="mt-0.5 shrink-0"
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggle(chunk.id)
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => {}}
                    className="size-3.5 accent-indigo-500"
                  />
                </div>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {/* Quality dot */}
                    <span
                      className={`mt-px shrink-0 size-2 rounded-full ${QUALITY_DOT[chunk.quality]}`}
                      title={chunk.quality}
                    />
                    {/* Index */}
                    <span className="shrink-0 text-[10px] text-muted-foreground">#{globalIdx}</span>
                    {/* Truncated content */}
                    <span className="truncate text-xs text-foreground">
                      {chunk.content.slice(0, 80)}
                      {chunk.content.length > 80 ? '…' : ''}
                    </span>
                  </div>

                  {/* Metadata line */}
                  <div className="mt-0.5 flex flex-wrap items-center gap-2 pl-4">
                    <span className="text-[10px] text-muted-foreground">
                      {chunk.tokens} tokens
                    </span>
                    {chunk.page_idx >= 0 && (
                      <span className="text-[10px] text-muted-foreground">p.{chunk.page_idx}</span>
                    )}
                    <span className="text-[10px] text-muted-foreground">{chunk.original_type}</span>
                    {chunk.is_multimodal && (
                      <span className="text-[10px] text-muted-foreground">multimodal</span>
                    )}
                  </div>

                  {/* Quality reason tags */}
                  {chunk.quality_reasons && chunk.quality_reasons.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1 pl-4">
                      {chunk.quality_reasons.map((r, i) => (
                        <span
                          key={i}
                          className={`rounded px-1.5 py-0.5 text-[9px] bg-muted ${QUALITY_LABEL[chunk.quality]}`}
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 border-t border-border px-3 py-2">
          <Button
            size="xs"
            variant="outline"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            ‹
          </Button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            let p: number
            if (totalPages <= 7) {
              p = i + 1
            } else if (page <= 4) {
              p = i + 1
            } else if (page >= totalPages - 3) {
              p = totalPages - 6 + i
            } else {
              p = page - 3 + i
            }
            return (
              <Button
                key={p}
                size="xs"
                variant={p === page ? 'default' : 'outline'}
                onClick={() => onPageChange(p)}
              >
                {p}
              </Button>
            )
          })}
          <Button
            size="xs"
            variant="outline"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            ›
          </Button>
        </div>
      )}
    </div>
  )
}
