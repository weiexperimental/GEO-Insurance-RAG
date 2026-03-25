import type { ChunkQualityStats } from '@/lib/types'

interface Props {
  stats: ChunkQualityStats | null
}

export function ChunksQualitySummary({ stats }: Props) {
  if (!stats) {
    return (
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        Loading stats…
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-4 text-xs">
      <span className="flex items-center gap-1.5">
        <span className="inline-block size-2.5 rounded-sm bg-green-500" />
        <span className="text-foreground font-medium">{stats.good}</span>
        <span className="text-muted-foreground">Good</span>
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block size-2.5 rounded-sm bg-yellow-500" />
        <span className="text-foreground font-medium">{stats.warning}</span>
        <span className="text-muted-foreground">Warning</span>
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block size-2.5 rounded-sm bg-red-500" />
        <span className="text-foreground font-medium">{stats.bad}</span>
        <span className="text-muted-foreground">Bad</span>
      </span>
      <span className="text-muted-foreground">/ {stats.total} total</span>
    </div>
  )
}
