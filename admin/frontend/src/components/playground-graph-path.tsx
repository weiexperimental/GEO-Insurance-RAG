'use client'
import dynamic from 'next/dynamic'
import type { PlaygroundEntity, PlaygroundRelationship } from '@/lib/types'
import type { GraphNode as RGNode, GraphEdge as RGEdge } from 'reagraph'

const GraphCanvas = dynamic(
  () => import('reagraph').then((m) => ({ default: m.GraphCanvas })),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-full text-muted-foreground text-[10px]">Loading...</div> },
)

const TYPE_COLORS: Record<string, string> = {
  organization: '#4ade80',
  concept: '#60a5fa',
  product: '#a78bfa',
  person: '#f472b6',
  location: '#fbbf24',
  event: '#fb923c',
  method: '#2dd4bf',
}
const DEFAULT_COLOR = '#666666'

interface Props {
  entities: PlaygroundEntity[]
  relationships: PlaygroundRelationship[]
}

export function PlaygroundGraphPath({ entities, relationships }: Props) {
  if (entities.length === 0) return null

  const nodeIds = new Set(entities.map((e) => e.entity_name))

  const rgNodes: RGNode[] = entities.map((e) => ({
    id: e.entity_name,
    label: e.entity_name,
    fill: TYPE_COLORS[e.entity_type] ?? DEFAULT_COLOR,
  }))

  const rgEdges: RGEdge[] = relationships
    .filter((r) => nodeIds.has(r.src_id) && nodeIds.has(r.tgt_id))
    .map((r, i) => ({
      id: `edge-${i}`,
      source: r.src_id,
      target: r.tgt_id,
      label: r.keywords || undefined,
    }))

  return (
    <div className="relative isolate rounded border border-border overflow-hidden" style={{ height: '200px', background: '#0a0a1a' }}>
      <GraphCanvas
        nodes={rgNodes}
        edges={rgEdges}
        theme={{
          canvas: { background: '#0a0a1a', fog: '#0a0a1a' },
          node: { fill: '#4a4a6a', activeFill: '#818cf8', opacity: 1, selectedOpacity: 1, inactiveOpacity: 0.3, label: { color: '#e2e8f0', activeColor: '#fff', stroke: '#0a0a1a' } },
          edge: { fill: '#374151', activeFill: '#6366f1', opacity: 0.7, selectedOpacity: 1, inactiveOpacity: 0.1, label: { color: '#94a3b8', activeColor: '#e2e8f0' } },
          ring: { fill: '#6366f1', activeFill: '#818cf8' },
          arrow: { fill: '#374151', activeFill: '#6366f1' },
          lasso: { background: 'rgba(99,102,241,0.1)', border: '#6366f1' },
        }}
        layoutType="forceDirected2d"
        labelType="auto"
      />
    </div>
  )
}
