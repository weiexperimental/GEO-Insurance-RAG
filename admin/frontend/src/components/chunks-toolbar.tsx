'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '@/hooks/use-api'
import { Button } from '@/components/ui/button'

interface Filters {
  doc_id: string
  type: string
  quality: string
  search: string
}

interface Props {
  checkedCount: number
  onFilterChange: (filters: Filters) => void
  onBatchDelete: () => void
}

const CHUNK_TYPES = ['text', 'table', 'list', 'image', 'header', 'footer', 'aside_text']

export function ChunksToolbar({ checkedCount, onFilterChange, onBatchDelete }: Props) {
  const [search, setSearch] = useState('')
  const [docId, setDocId] = useState('')
  const [type, setType] = useState('')
  const [quality, setQuality] = useState('')
  const [docs, setDocs] = useState<{ document_id: string; file_name: string }[]>([])
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const filtersRef = useRef<Filters>({ doc_id: '', type: '', quality: '', search: '' })

  useEffect(() => {
    api<{ documents: { document_id: string; file_name: string }[] }>('/api/documents?limit=200&offset=0')
      .then((d) => setDocs(d.documents))
      .catch(() => {})
  }, [])

  const notifyParent = useCallback(
    (newFilters: Filters) => {
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

  const handleDocChange = useCallback(
    (value: string) => {
      setDocId(value)
      notifyParent({ ...filtersRef.current, doc_id: value })
    },
    [notifyParent],
  )

  const handleTypeChange = useCallback(
    (value: string) => {
      setType(value)
      notifyParent({ ...filtersRef.current, type: value })
    },
    [notifyParent],
  )

  const handleQualityChange = useCallback(
    (value: string) => {
      setQuality(value)
      notifyParent({ ...filtersRef.current, quality: value })
    },
    [notifyParent],
  )

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-card px-3 py-2">
      {/* Search */}
      <input
        type="text"
        placeholder="Search chunks..."
        value={search}
        onChange={(e) => handleSearch(e.target.value)}
        className="w-48 rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />

      {/* Document dropdown */}
      <select
        value={docId}
        onChange={(e) => handleDocChange(e.target.value)}
        className="rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">All Documents</option>
        {docs.map((d) => (
          <option key={d.document_id} value={d.document_id}>
            {d.file_name}
          </option>
        ))}
      </select>

      {/* Type dropdown */}
      <select
        value={type}
        onChange={(e) => handleTypeChange(e.target.value)}
        className="rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">All Types</option>
        {CHUNK_TYPES.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      {/* Quality dropdown */}
      <select
        value={quality}
        onChange={(e) => handleQualityChange(e.target.value)}
        className="rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">All Quality</option>
        <option value="good">Good</option>
        <option value="warning">Warning</option>
        <option value="bad">Bad</option>
      </select>

      {/* Batch Delete */}
      <Button
        size="xs"
        variant="destructive"
        disabled={checkedCount === 0}
        onClick={onBatchDelete}
      >
        Batch Delete ({checkedCount})
      </Button>
    </div>
  )
}
