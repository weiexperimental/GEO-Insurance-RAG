'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/hooks/use-api'
import { useToast } from '@/hooks/use-toast'
import { DocToolbar } from '@/components/doc-toolbar'
import { DocTable } from '@/components/doc-table'
import { DocDetail } from '@/components/doc-detail'
import type { Document } from '@/lib/types'
import type { DocFilters } from '@/components/doc-toolbar'

const PAGE_SIZE = 20

function exportCSV(docs: Document[], chunkCounts: Record<string, number>) {
  const header = 'File,Status,Company,Product,Type,Chunks\n'
  const rows = docs.map((d) =>
    `"${d.file_name}","${d.status}","${d.metadata?.company || ''}","${d.metadata?.product_name || ''}","${d.metadata?.product_type || ''}","${chunkCounts[d.document_id] ?? 0}"`
  ).join('\n')
  const blob = new Blob([header + rows], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'documents.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export default function DocumentsPage() {
  const { toast } = useToast()
  const [docs, setDocs] = useState<Document[]>([])
  const [total, setTotal] = useState(0)
  const [chunkCounts, setChunkCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<DocFilters>({ search: '', status: '', productType: '' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)
  const filtersRef = useRef(filters)

  const fetchDocs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [listResult, counts] = await Promise.all([
        api<{ total: number; documents: Document[] }>('/api/documents?limit=200&offset=0'),
        api<Record<string, number>>('/api/documents/chunk-counts'),
      ])
      setDocs(listResult.documents)
      setTotal(listResult.total)
      setChunkCounts(counts)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDocs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleFilterChange = useCallback((newFilters: DocFilters) => {
    filtersRef.current = newFilters
    setFilters(newFilters)
    setPage(1)
    setCheckedIds(new Set())
  }, [])

  const handleSelect = useCallback((id: string) => {
    setSelectedId((prev) => (prev === id ? null : id))
  }, [])

  const handleToggle = useCallback((id: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) { next.delete(id) } else { next.add(id) }
      return next
    })
  }, [])

  const handleToggleAll = useCallback((checked: boolean) => {
    if (checked) {
      setCheckedIds(new Set(docs.map((d) => d.document_id)))
    } else {
      setCheckedIds(new Set())
    }
  }, [docs])

  const handleBatchDelete = useCallback(async () => {
    if (checkedIds.size === 0) return
    if (!window.confirm(`Delete ${checkedIds.size} document(s)? This will remove all chunks, entities, and relationships. This cannot be undone.`)) return
    const count = checkedIds.size
    let success = 0
    let failed = 0
    for (const id of Array.from(checkedIds)) {
      try {
        await api(`/api/documents/${id}`, { method: 'DELETE' })
        success++
      } catch {
        failed++
      }
    }
    if (selectedId && checkedIds.has(selectedId)) setSelectedId(null)
    setCheckedIds(new Set())
    if (failed === 0) {
      toast(`Deleted ${success} document${success !== 1 ? 's' : ''}`, 'success')
    } else {
      toast(`Deleted ${success}, failed ${failed}`, 'error')
    }
    await fetchDocs()
  }, [checkedIds, selectedId, fetchDocs, toast])

  const handleDetailDelete = useCallback(async () => {
    setSelectedId(null)
    await fetchDocs()
  }, [fetchDocs])

  const handleExportCSV = useCallback(() => {
    exportCSV(docs, chunkCounts)
  }, [docs, chunkCounts])

  return (
    <div className="flex flex-col gap-3 h-[calc(100vh-80px)]">
      {/* Toolbar */}
      <DocToolbar
        total={total}
        checkedCount={checkedIds.size}
        onFilterChange={handleFilterChange}
        onBatchDelete={handleBatchDelete}
        onExportCSV={handleExportCSV}
      />

      {/* Error */}
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      {/* Main two-column layout */}
      <div className="flex flex-1 gap-3 overflow-hidden">
        {/* Left: Documents table */}
        <div className="flex flex-1 min-w-0 flex-col overflow-hidden rounded-md border border-border bg-card">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
              Loading…
            </div>
          ) : (
            <DocTable
              docs={docs}
              chunkCounts={chunkCounts}
              selectedId={selectedId}
              checkedIds={checkedIds}
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              filters={filters}
              onSelect={handleSelect}
              onToggle={handleToggle}
              onToggleAll={handleToggleAll}
              onPageChange={setPage}
            />
          )}
        </div>

        {/* Right: Detail panel */}
        <div className="w-80 flex-shrink-0 overflow-y-auto rounded-md border border-border bg-card p-4">
          <div className="mb-3 text-[9px] uppercase tracking-wider text-muted-foreground">
            Document Detail
          </div>
          {selectedId ? (
            <DocDetail
              key={selectedId}
              docId={selectedId}
              onDelete={handleDetailDelete}
            />
          ) : (
            <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
              Click a document to see details
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
