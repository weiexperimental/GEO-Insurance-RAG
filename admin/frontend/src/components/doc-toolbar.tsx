'use client'
import { useState, useRef, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import type { Document } from '@/lib/types'

interface Props {
  total: number
  checkedCount: number
  onFilterChange: (filters: DocFilters) => void
  onBatchDelete: () => void
  onExportCSV: () => void
}

export interface DocFilters {
  search: string
  status: string
  productType: string
}

const PRODUCT_TYPES = ['危疾', '儲蓄', '人壽', '醫療', '年金']

export function DocToolbar({ total, checkedCount, onFilterChange, onBatchDelete, onExportCSV }: Props) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [productType, setProductType] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const filtersRef = useRef<DocFilters>({ search: '', status: '', productType: '' })

  const notifyParent = useCallback(
    (newFilters: DocFilters) => {
      filtersRef.current = newFilters
      onFilterChange(newFilters)
    },
    [onFilterChange],
  )

  const handleSearch = useCallback(
    (value: string) => {
      setSearch(value)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        notifyParent({ ...filtersRef.current, search: value })
      }, 300)
    },
    [notifyParent],
  )

  const handleStatusChange = useCallback(
    (value: string) => {
      setStatus(value)
      notifyParent({ ...filtersRef.current, status: value })
    },
    [notifyParent],
  )

  const handleTypeChange = useCallback(
    (value: string) => {
      setProductType(value)
      notifyParent({ ...filtersRef.current, productType: value })
    },
    [notifyParent],
  )

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-card px-3 py-2">
      <span className="text-xs text-muted-foreground mr-1">Documents ({total})</span>

      {/* Search */}
      <input
        type="text"
        placeholder="Search files..."
        value={search}
        onChange={(e) => handleSearch(e.target.value)}
        className="w-44 rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />

      {/* Status filter */}
      <select
        value={status}
        onChange={(e) => handleStatusChange(e.target.value)}
        className="rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">All Status</option>
        <option value="processed">Processed</option>
        <option value="pending">Pending</option>
        <option value="processing">Processing</option>
        <option value="failed">Failed</option>
      </select>

      {/* Product type filter */}
      <select
        value={productType}
        onChange={(e) => handleTypeChange(e.target.value)}
        className="rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">All Types</option>
        {PRODUCT_TYPES.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      <div className="flex-1" />

      {/* Batch Delete */}
      <Button
        size="xs"
        variant="destructive"
        disabled={checkedCount === 0}
        onClick={onBatchDelete}
      >
        Batch Delete ({checkedCount})
      </Button>

      {/* Export CSV */}
      <Button size="xs" variant="outline" onClick={onExportCSV}>
        Export CSV
      </Button>
    </div>
  )
}
