'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/hooks/use-api'
import { useToast } from '@/hooks/use-toast'
import { ChunksToolbar } from '@/components/chunks-toolbar'
import { ChunksQualitySummary } from '@/components/chunks-quality-summary'
import { ChunksList } from '@/components/chunks-list'
import { ChunkDetail } from '@/components/chunk-detail'
import type {
  ChunksListResponse,
  ChunkQualityStats,
  ChunkItem,
} from '@/lib/types'

interface Filters {
  doc_id: string
  type: string
  quality: string
  search: string
}

const PAGE_SIZE = 20

export default function ChunksPage() {
  const { toast } = useToast()
  const [filters, setFilters] = useState<Filters>({ doc_id: '', type: '', quality: '', search: '' })
  const [chunks, setChunks] = useState<ChunkItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [stats, setStats] = useState<ChunkQualityStats | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const filtersRef = useRef(filters)
  const pageRef = useRef(page)

  const fetchChunks = useCallback(async (f: Filters, p: number) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (f.doc_id) params.set('doc_id', f.doc_id)
      if (f.type) params.set('type', f.type)
      if (f.quality) params.set('quality', f.quality)
      if (f.search) params.set('search', f.search)
      params.set('page', String(p))
      params.set('size', String(PAGE_SIZE))

      const [listResult, statsResult] = await Promise.all([
        api<ChunksListResponse>(`/api/chunks?${params.toString()}`),
        api<ChunkQualityStats>(`/api/chunks/stats${f.doc_id ? `?doc_id=${f.doc_id}` : ''}`),
      ])
      setChunks(listResult.chunks)
      setTotal(listResult.total)
      setStats(statsResult)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load chunks')
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => {
    fetchChunks(filters, page)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleFilterChange = useCallback(
    (newFilters: Filters) => {
      filtersRef.current = newFilters
      pageRef.current = 1
      setFilters(newFilters)
      setPage(1)
      setCheckedIds(new Set())
      fetchChunks(newFilters, 1)
    },
    [fetchChunks],
  )

  const handlePageChange = useCallback(
    (newPage: number) => {
      pageRef.current = newPage
      setPage(newPage)
      setCheckedIds(new Set())
      fetchChunks(filtersRef.current, newPage)
    },
    [fetchChunks],
  )

  const handleSelect = useCallback((id: string) => {
    setSelectedId((prev) => (prev === id ? null : id))
  }, [])

  const handleToggle = useCallback((id: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const handleToggleAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        setCheckedIds(new Set(chunks.map((c) => c.id)))
      } else {
        setCheckedIds(new Set())
      }
    },
    [chunks],
  )

  const handleBatchDelete = useCallback(async () => {
    if (checkedIds.size === 0) return
    if (!window.confirm(`Delete ${checkedIds.size} chunk(s)? This cannot be undone.`)) return
    const count = checkedIds.size
    try {
      await api('/api/chunks/batch-delete', {
        method: 'POST',
        body: JSON.stringify({ chunk_ids: Array.from(checkedIds) }),
      })
      // Clear selections
      if (selectedId && checkedIds.has(selectedId)) {
        setSelectedId(null)
      }
      setCheckedIds(new Set())
      toast(`Deleted ${count} chunk${count !== 1 ? 's' : ''}`, 'success')
      fetchChunks(filtersRef.current, pageRef.current)
    } catch (e) {
      toast('Batch delete failed', 'error')
    }
  }, [checkedIds, selectedId, fetchChunks, toast])

  const handleDetailSave = useCallback(async () => {
    await fetchChunks(filtersRef.current, pageRef.current)
  }, [fetchChunks])

  const handleDetailDelete = useCallback(async () => {
    setSelectedId(null)
    await fetchChunks(filtersRef.current, pageRef.current)
  }, [fetchChunks])

  return (
    <div className="flex flex-col gap-3 h-[calc(100vh-80px)]">
      {/* Toolbar */}
      <ChunksToolbar
        checkedCount={checkedIds.size}
        onFilterChange={handleFilterChange}
        onBatchDelete={handleBatchDelete}
      />

      {/* Error */}
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      {/* Main two-column layout */}
      <div className="flex flex-1 gap-3 overflow-hidden">
        {/* Left: Quality Summary + List */}
        <div className="flex flex-1 min-w-0 flex-col overflow-hidden rounded-md border border-border bg-card">
          {/* Quality summary bar */}
          <div className="shrink-0 border-b border-border px-3 py-2">
            <ChunksQualitySummary stats={stats} />
          </div>

          {/* Chunks list */}
          <div className="flex-1 overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
                Loading…
              </div>
            ) : (
              <ChunksList
                chunks={chunks}
                total={total}
                page={page}
                size={PAGE_SIZE}
                selectedId={selectedId}
                checkedIds={checkedIds}
                onSelect={handleSelect}
                onToggle={handleToggle}
                onToggleAll={handleToggleAll}
                onPageChange={handlePageChange}
              />
            )}
          </div>
        </div>

        {/* Right: Detail panel */}
        <div className="w-80 flex-shrink-0 overflow-y-auto rounded-md border border-border bg-card p-4">
          <div className="mb-3 text-[9px] uppercase tracking-wider text-muted-foreground">
            Chunk Detail
          </div>
          {selectedId ? (
            <ChunkDetail
              key={selectedId}
              chunkId={selectedId}
              onSave={handleDetailSave}
              onDelete={handleDetailDelete}
            />
          ) : (
            <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
              Click a chunk to see details
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
