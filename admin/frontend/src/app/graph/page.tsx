'use client'
import { useState, useCallback } from 'react'
import { GraphViewer } from '@/components/graph-viewer'
import { NodeDetail } from '@/components/node-detail'
import { EdgeDetail } from '@/components/edge-detail'
import { DeleteConfirmModal } from '@/components/delete-confirm-modal'
import { EditEntityModal } from '@/components/edit-entity-modal'
import { MergeEntityModal } from '@/components/merge-entity-modal'
import type { GraphNode, GraphEdge } from '@/lib/types'

// ─── modal state type ─────────────────────────────────────────────────────────

type ModalState =
  | { type: 'edit-entity'; node: GraphNode }
  | { type: 'merge-entity'; node: GraphNode }
  | { type: 'delete-entity'; node: GraphNode }
  | { type: 'delete-relation'; edge: GraphEdge }
  | null

// ─── page ─────────────────────────────────────────────────────────────────────

export default function GraphPage() {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null)
  const [modal, setModal] = useState<ModalState>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node)
    setSelectedEdge(null)
  }, [])

  const handleEdgeClick = useCallback((edge: GraphEdge) => {
    setSelectedEdge(edge)
    setSelectedNode(null)
  }, [])

  const handleNavigate = useCallback((entityId: string) => {
    // TODO Task 8: focus the graph canvas on the entity
    console.log('[graph] navigate to entity:', entityId)
  }, [])

  const handleEdit = useCallback((node: GraphNode) => {
    setModal({ type: 'edit-entity', node })
  }, [])

  const handleDelete = useCallback((node: GraphNode) => {
    setModal({ type: 'delete-entity', node })
  }, [])

  const handleMerge = useCallback((node: GraphNode) => {
    setModal({ type: 'merge-entity', node })
  }, [])

  const handleEdgeDelete = useCallback((edge: GraphEdge) => {
    setModal({ type: 'delete-relation', edge })
  }, [])

  function closeModal() {
    setModal(null)
  }

  function closeAndRefresh() {
    setModal(null)
    setSelectedNode(null)
    setSelectedEdge(null)
    setRefreshKey((k) => k + 1)
  }

  const showNode = selectedNode !== null
  const showEdge = !showNode && selectedEdge !== null

  return (
    <>
      <div className="flex h-[calc(100vh-80px)] gap-4 overflow-hidden">
        {/* Graph canvas — takes remaining width */}
        <div className="flex-1 min-w-0 overflow-hidden">
          <GraphViewer
            key={refreshKey}
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
          />
        </div>

        {/* Right sidebar */}
        <div className="w-72 flex-shrink-0 overflow-y-auto rounded-md border border-border bg-card p-4">
          <div className="mb-3 text-[9px] uppercase tracking-wider text-muted-foreground">
            {showNode ? 'Node Detail' : showEdge ? 'Edge Detail' : 'Detail'}
          </div>

          {showNode && (
            <NodeDetail
              node={selectedNode}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onMerge={handleMerge}
              onNavigate={handleNavigate}
            />
          )}

          {showEdge && (
            <EdgeDetail
              edge={selectedEdge}
              onDelete={handleEdgeDelete}
            />
          )}

          {!showNode && !showEdge && (
            <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
              Click a node or edge to see details
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      {modal?.type === 'edit-entity' && (
        <EditEntityModal
          node={modal.node}
          onSave={closeAndRefresh}
          onCancel={closeModal}
        />
      )}

      {modal?.type === 'merge-entity' && (
        <MergeEntityModal
          node={modal.node}
          onSave={closeAndRefresh}
          onCancel={closeModal}
        />
      )}

      {modal?.type === 'delete-entity' && (
        <DeleteConfirmModal
          type="entity"
          name={modal.node.id}
          onConfirm={closeAndRefresh}
          onCancel={closeModal}
        />
      )}

      {modal?.type === 'delete-relation' && (
        <DeleteConfirmModal
          type="relation"
          name={modal.edge.id}
          source={modal.edge.source}
          target={modal.edge.target}
          onConfirm={closeAndRefresh}
          onCancel={closeModal}
        />
      )}
    </>
  )
}
