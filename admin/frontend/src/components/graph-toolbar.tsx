'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '@/hooks/use-api'

const TYPE_COLORS: Record<string, string> = {
  organization: '#4ade80',
  concept: '#60a5fa',
  product: '#a78bfa',
  person: '#f472b6',
  location: '#fbbf24',
  event: '#fb923c',
  method: '#2dd4bf',
}

const DEFAULT_HIDDEN = new Set(['footer', 'header', 'aside_text', 'content', 'data', 'UNKNOWN'])

interface Props {
  onFilterChange: (types: string[], doc: string) => void
  onSearchSelect: (entityId: string) => void
  entityTypes: string[]
}

export function GraphToolbar({ onFilterChange, onSearchSelect, entityTypes }: Props) {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set(DEFAULT_HIDDEN))
  const [selectedDoc, setSelectedDoc] = useState('')
  const [docs, setDocs] = useState<{ document_id: string; file_name: string }[]>([])
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Fetch document list for the dropdown
  useEffect(() => {
    api<{ documents: { document_id: string; file_name: string }[] }>('/api/documents?limit=200&offset=0')
      .then((d) => setDocs(d.documents))
      .catch(() => {})
  }, [])

  // Notify parent when filters change
  useEffect(() => {
    const activeTypes = entityTypes.filter((t) => !hiddenTypes.has(t))
    onFilterChange(activeTypes, selectedDoc)
  }, [hiddenTypes, selectedDoc, entityTypes, onFilterChange])

  const handleSearchInput = useCallback((value: string) => {
    setQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (value.length < 2) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await api<string[]>(`/api/graph/search?q=${encodeURIComponent(value)}`)
        setSuggestions(results)
        setShowSuggestions(true)
      } catch {
        setSuggestions([])
      }
    }, 300)
  }, [])

  const handleSelect = useCallback(
    (entityId: string) => {
      onSearchSelect(entityId)
      setQuery(entityId)
      setShowSuggestions(false)
    },
    [onSearchSelect],
  )

  const toggleType = useCallback((type: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }, [])

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border bg-card p-3">
      {/* Search bar */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search entities..."
          value={query}
          onChange={(e) => handleSearchInput(e.target.value)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          className="w-full rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded border border-border bg-card shadow-lg">
            {suggestions.map((s) => (
              <button
                key={s}
                onMouseDown={() => handleSelect(s)}
                className="block w-full px-3 py-1.5 text-left text-xs hover:bg-muted"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Document filter */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Document:</span>
        <select
          className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          value={selectedDoc}
          onChange={(e) => setSelectedDoc(e.target.value)}
        >
          <option value="">All documents</option>
          {docs.map((d) => (
            <option key={d.document_id} value={d.document_id}>
              {d.file_name}
            </option>
          ))}
        </select>
      </div>

      {/* Type filter chips */}
      {entityTypes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {entityTypes.map((type) => {
            const hidden = hiddenTypes.has(type)
            const color = TYPE_COLORS[type] || '#94a3b8'
            return (
              <button
                key={type}
                onClick={() => toggleType(type)}
                title={hidden ? `Show ${type}` : `Hide ${type}`}
                className="rounded-full border px-2 py-0.5 text-[10px] font-medium transition-opacity"
                style={
                  hidden
                    ? {
                        borderColor: '#4b5563',
                        color: '#6b7280',
                        textDecoration: 'line-through',
                        backgroundColor: 'transparent',
                      }
                    : {
                        borderColor: color,
                        color: color,
                        backgroundColor: `${color}1a`,
                      }
                }
              >
                {type}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
