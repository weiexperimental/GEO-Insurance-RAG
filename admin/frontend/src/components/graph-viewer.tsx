'use client'
import dynamic from 'next/dynamic'
import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/hooks/use-api'
import type { GraphNode as AppGraphNode, GraphEdge as AppGraphEdge, GraphData } from '@/lib/types'
import type { GraphNode as RGNode, GraphEdge as RGEdge, InternalGraphNode, InternalGraphEdge, Theme } from 'reagraph'
import { GraphToolbar } from './graph-toolbar'

// Dynamically import GraphCanvas — it uses WebGL and cannot run on the server
const GraphCanvas = dynamic(
  () => import('reagraph').then((m) => {
    const Comp = m.GraphCanvas
    return { default: Comp }
  }),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-full text-muted-foreground text-xs">Loading graph...</div> },
)

// ─── constants ────────────────────────────────────────────────────────────────

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

const DARK_THEME: Theme = {
  canvas: {
    background: '#0a0a1a',
    fog: '#0a0a1a',
  },
  node: {
    fill: '#4a4a6a',
    activeFill: '#818cf8',
    opacity: 1,
    selectedOpacity: 1,
    inactiveOpacity: 0.3,
    label: {
      color: '#e2e8f0',
      activeColor: '#ffffff',
      stroke: '#0a0a1a',
    },
  },
  ring: {
    fill: '#6366f1',
    activeFill: '#818cf8',
  },
  edge: {
    fill: '#374151',
    activeFill: '#6366f1',
    opacity: 0.7,
    selectedOpacity: 1,
    inactiveOpacity: 0.1,
    label: {
      color: '#94a3b8',
      activeColor: '#e2e8f0',
    },
  },
  arrow: {
    fill: '#374151',
    activeFill: '#6366f1',
  },
  lasso: {
    background: 'rgba(99,102,241,0.1)',
    border: '#6366f1',
  },
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function toRGNode(n: AppGraphNode): RGNode {
  return {
    id: n.id,
    label: n.id,
    fill: TYPE_COLORS[n.entity_type] ?? DEFAULT_COLOR,
    data: n,
  }
}

function toRGEdge(e: AppGraphEdge): RGEdge {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.keywords || undefined,
    data: e,
  }
}

// ─── props ────────────────────────────────────────────────────────────────────

interface Props {
  onNodeClick?: (node: AppGraphNode) => void
  onEdgeClick?: (edge: AppGraphEdge) => void
}

// ─── component ────────────────────────────────────────────────────────────────

export function GraphViewer({ onNodeClick, onEdgeClick }: Props) {
  const [rawData, setRawData] = useState<GraphData>({ nodes: [], edges: [] })
  const [entityTypes, setEntityTypes] = useState<string[]>([])
  const [activeTypes, setActiveTypes] = useState<string[]>([])
  const [filterDoc, setFilterDoc] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const focusRef = useRef<string | null>(null)

  // Derive the sorted, unique entity types from loaded data
  useEffect(() => {
    const types = Array.from(new Set(rawData.nodes.map((n) => n.entity_type))).sort()
    setEntityTypes(types)
  }, [rawData])

  // Fetch graph data whenever filter changes
  const fetchGraph = useCallback(
    async (types: string[], doc: string) => {
      setLoading(true)
      setError(null)
      try {
        const params = new URLSearchParams({ max_nodes: '300' })
        if (types.length > 0) params.set('types', types.join(','))
        if (doc) params.set('doc', doc)
        const data = await api<GraphData>(`/api/graph?${params.toString()}`)
        setRawData(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load graph')
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  // Initial load
  useEffect(() => {
    fetchGraph([], '')
  }, [fetchGraph])

  const handleFilterChange = useCallback(
    (types: string[], doc: string) => {
      setActiveTypes(types)
      setFilterDoc(doc)
      fetchGraph(types, doc)
    },
    [fetchGraph],
  )

  const handleSearchSelect = useCallback((entityId: string) => {
    focusRef.current = entityId
  }, [])

  // Build Reagraph-compatible nodes/edges, filtered by active types
  const rgNodes: RGNode[] = rawData.nodes
    .filter((n) => activeTypes.length === 0 || activeTypes.includes(n.entity_type))
    .map(toRGNode)

  const rgNodeIds = new Set(rgNodes.map((n) => n.id))

  const rgEdges: RGEdge[] = rawData.edges
    .filter((e) => rgNodeIds.has(e.source) && rgNodeIds.has(e.target))
    .map(toRGEdge)

  const handleNodeClick = useCallback(
    (node: InternalGraphNode) => {
      onNodeClick?.(node.data as AppGraphNode)
    },
    [onNodeClick],
  )

  const handleEdgeClick = useCallback(
    (edge: InternalGraphEdge) => {
      onEdgeClick?.(edge.data as AppGraphEdge)
    },
    [onEdgeClick],
  )

  return (
    <div className="flex flex-col gap-3">
      <GraphToolbar
        onFilterChange={handleFilterChange}
        onSearchSelect={handleSearchSelect}
        entityTypes={entityTypes}
      />

      <div
        className="relative rounded-md border border-border overflow-hidden"
        style={{ height: '560px', background: '#0a0a1a' }}
      >
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40">
            <span className="text-xs text-muted-foreground">Loading graph…</span>
          </div>
        )}
        {error && rgNodes.length === 0 && (
          <div className="absolute inset-0 z-10 flex items-center justify-center">
            <span className="text-xs text-destructive">{error}</span>
          </div>
        )}
        {!loading && !error && rgNodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs text-muted-foreground">No graph data</span>
          </div>
        )}
        {rgNodes.length > 0 && (
          <GraphCanvas
            nodes={rgNodes}
            edges={rgEdges}
            theme={DARK_THEME}
            layoutType="forceDirected2d"
            draggable
            labelType="auto"
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
          />
        )}
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 px-1 text-[11px] text-muted-foreground">
        <span>{rgNodes.length} nodes</span>
        <span>{rgEdges.length} edges</span>
        {filterDoc && <span>Filtered by document</span>}
      </div>
    </div>
  )
}
