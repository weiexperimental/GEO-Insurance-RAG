'use client'
import { useState, useCallback, useMemo } from 'react'
import type { Document } from '@/lib/types'
import type { DocFilters } from '@/components/doc-toolbar'

interface Props {
  docs: Document[]
  chunkCounts: Record<string, number>
  selectedId: string | null
  checkedIds: Set<string>
  page: number
  pageSize: number
  total: number
  filters: DocFilters
  onSelect: (id: string) => void
  onToggle: (id: string) => void
  onToggleAll: (checked: boolean) => void
  onPageChange: (page: number) => void
}

type SortField = 'file_name' | 'status' | 'company' | 'product_type' | 'chunks' | 'updated_at'
type SortDir = 'asc' | 'desc'

const statusBadge: Record<string, string> = {
  processed: 'bg-[hsl(var(--success))]/20 text-[hsl(var(--success))]',
  failed: 'bg-[hsl(var(--error))]/20 text-[hsl(var(--error))]',
  pending: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
  processing: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
  preprocessed: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
}

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '—'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function DocTable({
  docs,
  chunkCounts,
  selectedId,
  checkedIds,
  page,
  pageSize,
  total,
  filters,
  onSelect,
  onToggle,
  onToggleAll,
  onPageChange,
}: Props) {
  const [sortField, setSortField] = useState<SortField>('updated_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const handleSort = useCallback((field: SortField) => {
    setSortField((prev) => {
      if (prev === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
        return prev
      }
      setSortDir('asc')
      return field
    })
  }, [])

  // Client-side filtering
  const filtered = useMemo(() => {
    let result = docs
    if (filters.search) {
      const q = filters.search.toLowerCase()
      result = result.filter((d) => d.file_name.toLowerCase().includes(q))
    }
    if (filters.status) {
      result = result.filter((d) => d.status === filters.status)
    }
    if (filters.productType) {
      result = result.filter((d) =>
        (d.metadata?.product_type || '').includes(filters.productType)
      )
    }
    return result
  }, [docs, filters])

  // Client-side sorting
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let av: string | number = ''
      let bv: string | number = ''
      switch (sortField) {
        case 'file_name': av = a.file_name; bv = b.file_name; break
        case 'status': av = a.status; bv = b.status; break
        case 'company': av = a.metadata?.company || ''; bv = b.metadata?.company || ''; break
        case 'product_type': av = a.metadata?.product_type || ''; bv = b.metadata?.product_type || ''; break
        case 'chunks': av = chunkCounts[a.document_id] ?? 0; bv = chunkCounts[b.document_id] ?? 0; break
        case 'updated_at': av = a.updated_at || ''; bv = b.updated_at || ''; break
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [filtered, sortField, sortDir, chunkCounts])

  // Pagination (client-side on filtered+sorted)
  const totalFiltered = sorted.length
  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize))
  const pageStart = (page - 1) * pageSize
  const pageItems = sorted.slice(pageStart, pageStart + pageSize)

  const allChecked = pageItems.length > 0 && pageItems.every((d) => checkedIds.has(d.document_id))

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="ml-0.5 text-muted-foreground/40">↕</span>
    return <span className="ml-0.5">{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  const thClass = 'px-3 py-2 text-left text-[10px] font-medium text-muted-foreground cursor-pointer select-none hover:text-foreground'

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="bg-muted sticky top-0 z-10">
            <tr>
              <th className="px-3 py-2 w-8">
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={(e) => onToggleAll(e.target.checked)}
                  className="accent-primary"
                />
              </th>
              <th className={thClass} onClick={() => handleSort('file_name')}>
                File <SortIcon field="file_name" />
              </th>
              <th className={thClass} onClick={() => handleSort('status')}>
                Status <SortIcon field="status" />
              </th>
              <th className={thClass} onClick={() => handleSort('chunks')}>
                Chunks <SortIcon field="chunks" />
              </th>
              <th className={thClass + ' hidden sm:table-cell'} onClick={() => handleSort('company')}>
                Company <SortIcon field="company" />
              </th>
              <th className={thClass + ' hidden md:table-cell'} onClick={() => handleSort('product_type')}>
                Type <SortIcon field="product_type" />
              </th>
              <th className={thClass + ' hidden lg:table-cell'} onClick={() => handleSort('updated_at')}>
                Updated <SortIcon field="updated_at" />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {pageItems.map((doc) => {
              const chunks = chunkCounts[doc.document_id] ?? null
              const isSelected = doc.document_id === selectedId
              const isChecked = checkedIds.has(doc.document_id)
              const isHealthy = chunks !== null && chunks > 0
              const hasChunkData = chunks !== null

              return (
                <tr
                  key={doc.document_id}
                  className={`cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-accent/20 border-l-2 border-l-primary'
                      : 'hover:bg-muted/40'
                  }`}
                  onClick={() => onSelect(doc.document_id)}
                >
                  <td
                    className="px-3 py-2 w-8"
                    onClick={(e) => { e.stopPropagation(); onToggle(doc.document_id) }}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => onToggle(doc.document_id)}
                      className="accent-primary"
                    />
                  </td>
                  <td className="px-3 py-2 max-w-[180px]">
                    <span className="block truncate font-mono text-[11px]" title={doc.file_name}>
                      {doc.file_name}
                    </span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] ${statusBadge[doc.status] || 'bg-muted text-muted-foreground'}`}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      {hasChunkData ? (
                        <>
                          <span className={`inline-block h-1.5 w-1.5 rounded-full flex-shrink-0 ${isHealthy ? 'bg-green-400' : 'bg-red-400'}`} />
                          <span className={isHealthy ? 'text-foreground' : 'text-red-400'}>{chunks}</span>
                        </>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </span>
                  </td>
                  <td className="px-3 py-2 hidden sm:table-cell text-muted-foreground">
                    {doc.metadata?.company || '—'}
                  </td>
                  <td className="px-3 py-2 hidden md:table-cell text-muted-foreground">
                    {doc.metadata?.product_type || '—'}
                  </td>
                  <td className="px-3 py-2 hidden lg:table-cell text-muted-foreground">
                    {timeAgo(doc.updated_at)}
                  </td>
                </tr>
              )
            })}
            {pageItems.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-xs text-muted-foreground">
                  No documents match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border px-3 py-2 text-xs text-muted-foreground shrink-0">
          <span>{totalFiltered} documents</span>
          <div className="flex items-center gap-1">
            <button
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="rounded px-2 py-0.5 hover:bg-muted disabled:opacity-40"
            >
              ‹
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() => onPageChange(p)}
                className={`rounded px-2 py-0.5 ${p === page ? 'bg-accent text-foreground' : 'hover:bg-muted'}`}
              >
                {p}
              </button>
            ))}
            <button
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
              className="rounded px-2 py-0.5 hover:bg-muted disabled:opacity-40"
            >
              ›
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
