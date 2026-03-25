import type { SystemHealth } from '@/lib/types'

const statusColor: Record<string, string> = {
  green: 'text-[hsl(var(--success))]',
  yellow: 'text-[hsl(var(--warning))]',
  red: 'text-[hsl(var(--error))]',
  disconnected: 'text-[hsl(var(--error))]',
}

export function SystemHealthBar({ data }: { data: SystemHealth | null }) {
  if (!data) return <div className="text-xs text-muted-foreground">Loading...</div>

  const status = data.cluster?.status || 'disconnected'
  const firstNode = Object.values(data.nodes?.nodes || {})[0] as any
  const jvmPercent = firstNode?.jvm?.mem?.heap_used_percent ?? '—'
  const diskAvail = firstNode?.fs?.total?.available_in_bytes
  const diskFree = diskAvail ? `${(diskAvail / 1e9).toFixed(0)}GB` : '—'

  return (
    <div className="flex items-center gap-6 rounded-md border border-border bg-card px-4 py-2 font-mono text-xs">
      <span><span className={statusColor[status]}>●</span> opensearch {status}</span>
      <span className="text-muted-foreground">│</span>
      <span>JVM: {jvmPercent}%</span>
      <span className="text-muted-foreground">│</span>
      <span>Disk: {diskFree} free</span>
    </div>
  )
}
