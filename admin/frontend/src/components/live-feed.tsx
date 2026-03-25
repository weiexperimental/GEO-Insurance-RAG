import type { IngestionStatus } from '@/lib/types'

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  pending: { label: 'Pending', color: 'text-[hsl(var(--warning))]', icon: '⏳' },
  processing: { label: 'Processing', color: 'text-[hsl(var(--warning))]', icon: '▶' },
  preprocessed: { label: 'Partial', color: 'text-[hsl(var(--warning))]', icon: '◐' },
}

export function LiveFeed({ data }: { data: IngestionStatus | null }) {
  const items = data?.active || []
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <div className="mb-3 text-[9px] uppercase tracking-wider text-muted-foreground">
        Live Ingestion
      </div>
      <div className="space-y-2 font-mono text-xs">
        {items.length === 0 && (
          <div className="text-muted-foreground">No active ingestions</div>
        )}
        {items.map((item) => {
          const cfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.processing
          const elapsed = item.created_at
            ? Math.round((Date.now() - new Date(item.created_at).getTime()) / 1000)
            : 0
          const elapsedStr = elapsed > 60
            ? `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`
            : `${elapsed}s`

          return (
            <div key={item.document_id} className="rounded bg-black/30 p-3">
              <div className="flex items-center gap-2">
                <span className={cfg.color}>{cfg.icon}</span>
                <span className="flex-1 truncate">{item.file_name}</span>
                <span className={`text-[10px] ${cfg.color}`}>{cfg.label}</span>
                <span className="text-[10px] text-muted-foreground">{elapsedStr}</span>
              </div>
              {item.status === 'processing' && (
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-[hsl(var(--warning))]"
                    style={{
                      width: '100%',
                      animation: 'pulse 2s ease-in-out infinite',
                    }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
