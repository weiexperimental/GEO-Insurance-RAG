'use client'
import { useState, useCallback } from 'react'
import { api } from '@/hooks/use-api'
import { Button } from '@/components/ui/button'
import type { GraphNode } from '@/lib/types'

// ─── props ────────────────────────────────────────────────────────────────────

interface Props {
  node: GraphNode
  onSave: () => void
  onCancel: () => void
}

interface SearchResult {
  id: string
  entity_type: string
  description: string
}

// ─── component ────────────────────────────────────────────────────────────────

export function MergeEntityModal({ node, onSave, onCancel }: Props) {
  const [targetName, setTargetName] = useState(node.id)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [searching, setSearching] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = useCallback(async (q: string) => {
    setSearchQuery(q)
    if (!q.trim()) {
      setSearchResults([])
      return
    }
    setSearching(true)
    try {
      const data = await api<{ nodes?: SearchResult[]; results?: SearchResult[] }>(
        `/api/graph/search?q=${encodeURIComponent(q)}`
      )
      // Accept either `nodes` or `results` array shape
      const items = data.nodes ?? data.results ?? (Array.isArray(data) ? (data as SearchResult[]) : [])
      // Exclude current node from results
      setSearchResults(items.filter((r) => r.id !== node.id))
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }, [node.id])

  function toggleSource(id: string) {
    setSelectedSources((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    )
  }

  async function handleMerge() {
    if (selectedSources.length === 0) {
      setError('Select at least one entity to merge.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api('/api/graph/entity/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_entities: selectedSources,
          target_entity: targetName,
        }),
      })
      onSave()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Merge failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onCancel}
    >
      <div
        className="flex w-full max-w-lg flex-col gap-4 rounded-lg border border-border bg-card p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Title */}
        <div className="text-sm font-semibold text-foreground">
          Merge Entities into{' '}
          <span className="font-mono text-xs text-muted-foreground">{node.id}</span>
        </div>

        {/* Target name */}
        <div className="space-y-1.5">
          <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Target Entity Name
          </label>
          <input
            type="text"
            value={targetName}
            onChange={(e) => setTargetName(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
          />
        </div>

        {/* Search */}
        <div className="space-y-1.5">
          <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Search Entities to Merge
          </label>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Type to search…"
            className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
          />
          {searching && (
            <div className="text-xs text-muted-foreground">Searching…</div>
          )}
          {!searching && searchResults.length > 0 && (
            <ul className="max-h-36 overflow-y-auto rounded-md border border-border bg-background">
              {searchResults.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => toggleSource(r.id)}
                    className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors hover:bg-muted ${
                      selectedSources.includes(r.id) ? 'bg-yellow-500/10 text-yellow-300' : 'text-foreground'
                    }`}
                  >
                    <span className="w-3 shrink-0 text-center">
                      {selectedSources.includes(r.id) ? '✓' : ''}
                    </span>
                    <span className="truncate font-medium">{r.id}</span>
                    <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                      {r.entity_type}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Selected sources */}
        {selectedSources.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Will Merge ({selectedSources.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {selectedSources.map((s) => (
                <button
                  key={s}
                  onClick={() => toggleSource(s)}
                  className="inline-flex items-center gap-1 rounded-full border border-yellow-500/40 bg-yellow-500/10 px-2 py-0.5 text-[10px] text-yellow-300 hover:bg-yellow-500/20"
                >
                  {s}
                  <span className="text-yellow-500/70">×</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 border-t border-border pt-2">
          <Button size="xs" variant="outline" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button
            size="xs"
            className="border-yellow-500/60 bg-transparent text-yellow-400 hover:bg-yellow-500/10"
            onClick={handleMerge}
            disabled={loading || selectedSources.length === 0}
          >
            {loading ? 'Merging…' : `Merge ${selectedSources.length > 0 ? `(${selectedSources.length})` : ''}`}
          </Button>
        </div>
      </div>
    </div>
  )
}
