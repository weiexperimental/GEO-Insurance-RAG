import type { PlaygroundTiming, PlaygroundProcessingInfo } from '@/lib/types'

interface Props {
  timing: PlaygroundTiming
  processingInfo: PlaygroundProcessingInfo
}

function fmt(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}

export function PlaygroundStatsBar({ timing, processingInfo }: Props) {
  const pi = processingInfo
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-muted-foreground">
      {timing.total_ms != null && <span>Total: {fmt(timing.total_ms)}</span>}
      {timing.retrieval_ms != null && <span>Retrieval: {fmt(timing.retrieval_ms)}</span>}
      {pi.total_entities_found != null && (
        <span>{pi.total_entities_found}→{pi.entities_after_truncation} entities</span>
      )}
      {pi.merged_chunks_count != null && (
        <span>{pi.merged_chunks_count}→{pi.final_chunks_count} chunks</span>
      )}
    </div>
  )
}
