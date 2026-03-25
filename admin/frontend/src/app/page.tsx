'use client'
import { StatsCard } from '@/components/stats-card'
import { SystemHealthBar } from '@/components/system-health'
import { LiveFeed } from '@/components/live-feed'
import { useDashboardWs } from '@/hooks/use-dashboard-ws'

export default function OverviewPage() {
  const { systemHealth, ingestion } = useDashboardWs()
  const o = systemHealth?.overview

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <StatsCard label="Documents" value={o?.documents ?? '—'} />
        <StatsCard label="Entities" value={o?.entities ?? '—'} />
        <StatsCard label="Relationships" value={o?.relationships ?? '—'} />
        <StatsCard label="Index Size" value={o?.index_size ?? '—'} />
      </div>
      <div className="grid grid-cols-4 gap-3">
        <StatsCard label="Chunks" value={o?.chunks ?? '—'} />
        <StatsCard label="Pending" value={o?.pending ?? '0'} color="text-[hsl(var(--warning))]" />
        <StatsCard label="Failed" value={o?.failed ?? '0'} color="text-[hsl(var(--error))]" />
        <StatsCard label="LLM Cache" value={o?.llm_cache ?? '—'} />
      </div>
      <SystemHealthBar data={systemHealth} />
      <LiveFeed data={ingestion} />
    </div>
  )
}
