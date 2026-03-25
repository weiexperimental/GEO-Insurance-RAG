'use client'
import { useState, useCallback } from 'react'
import type { PlaygroundQueryRequest } from '@/lib/types'

interface Props {
  onRun: (params: PlaygroundQueryRequest) => void
  onRetrieveOnly: (params: PlaygroundQueryRequest) => void
  onCompare: (query: string, paramsA: Omit<PlaygroundQueryRequest, 'query'>, paramsB: Omit<PlaygroundQueryRequest, 'query'>) => void
  loading: boolean
}

const MODES = ['local', 'global', 'hybrid', 'naive', 'mix'] as const

export function PlaygroundQueryBar({ onRun, onRetrieveOnly, onCompare, loading }: Props) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<typeof MODES[number]>('hybrid')
  const [topK, setTopK] = useState(5)
  const [chunkTopK, setChunkTopK] = useState(10)
  const [rerank, setRerank] = useState(true)
  const [compareMode, setCompareMode] = useState(false)
  const [modeB, setModeB] = useState<typeof MODES[number]>('naive')
  const [topKB, setTopKB] = useState(10)
  const [chunkTopKB, setChunkTopKB] = useState(20)
  const [rerankB, setRerankB] = useState(false)

  const buildParams = useCallback((): PlaygroundQueryRequest => ({
    query, mode, top_k: topK, chunk_top_k: chunkTopK, enable_rerank: rerank,
  }), [query, mode, topK, chunkTopK, rerank])

  const handleRun = useCallback(() => {
    if (!query.trim() || loading) return
    onRun(buildParams())
  }, [query, loading, onRun, buildParams])

  const handleRetrieveOnly = useCallback(() => {
    if (!query.trim() || loading) return
    onRetrieveOnly(buildParams())
  }, [query, loading, onRetrieveOnly, buildParams])

  const handleCompare = useCallback(() => {
    if (!query.trim() || loading) return
    onCompare(
      query,
      { mode, top_k: topK, chunk_top_k: chunkTopK, enable_rerank: rerank },
      { mode: modeB, top_k: topKB, chunk_top_k: chunkTopKB, enable_rerank: rerankB },
    )
  }, [query, loading, onCompare, mode, topK, chunkTopK, rerank, modeB, topKB, chunkTopKB, rerankB])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (compareMode) handleCompare()
      else handleRun()
    }
  }, [compareMode, handleRun, handleCompare])

  return (
    <div className="space-y-3 rounded-md border border-border bg-card p-4">
      {/* Query input */}
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Enter query..."
        className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />

      {/* Params row A */}
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <label className="text-muted-foreground">
          {compareMode ? 'A:' : ''} Mode
          <select value={mode} onChange={(e) => setMode(e.target.value as typeof MODES[number])}
            className="ml-1 rounded border border-border bg-background px-2 py-1 text-xs">
            {MODES.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label className="text-muted-foreground">
          top_k
          <input type="number" min={1} max={50} value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="ml-1 w-14 rounded border border-border bg-background px-2 py-1 text-xs" />
        </label>
        <label className="text-muted-foreground">
          chunk_top_k
          <input type="number" min={1} max={100} value={chunkTopK}
            onChange={(e) => setChunkTopK(Number(e.target.value))}
            className="ml-1 w-14 rounded border border-border bg-background px-2 py-1 text-xs" />
        </label>
        <label className="flex items-center gap-1 text-muted-foreground">
          <input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} />
          Rerank
        </label>
      </div>

      {/* Params row B (compare mode only) */}
      {compareMode && (
        <div className="flex flex-wrap items-center gap-3 text-xs border-t border-border pt-3">
          <label className="text-muted-foreground">
            B: Mode
            <select value={modeB} onChange={(e) => setModeB(e.target.value as typeof MODES[number])}
              className="ml-1 rounded border border-border bg-background px-2 py-1 text-xs">
              {MODES.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <label className="text-muted-foreground">
            top_k
            <input type="number" min={1} max={50} value={topKB}
              onChange={(e) => setTopKB(Number(e.target.value))}
              className="ml-1 w-14 rounded border border-border bg-background px-2 py-1 text-xs" />
          </label>
          <label className="text-muted-foreground">
            chunk_top_k
            <input type="number" min={1} max={100} value={chunkTopKB}
              onChange={(e) => setChunkTopKB(Number(e.target.value))}
              className="ml-1 w-14 rounded border border-border bg-background px-2 py-1 text-xs" />
          </label>
          <label className="flex items-center gap-1 text-muted-foreground">
            <input type="checkbox" checked={rerankB} onChange={(e) => setRerankB(e.target.checked)} />
            Rerank
          </label>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        {compareMode ? (
          <button onClick={handleCompare} disabled={loading || !query.trim()}
            className="rounded bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {loading ? 'Running...' : 'Compare'}
          </button>
        ) : (
          <>
            <button onClick={handleRun} disabled={loading || !query.trim()}
              className="rounded bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
              {loading ? 'Running...' : 'Run'}
            </button>
            <button onClick={handleRetrieveOnly} disabled={loading || !query.trim()}
              className="rounded border border-border px-4 py-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50">
              Retrieve Only
            </button>
          </>
        )}
        <button
          onClick={() => setCompareMode(!compareMode)}
          className={`ml-auto rounded border px-3 py-1.5 text-xs ${
            compareMode ? 'border-indigo-500 text-indigo-400' : 'border-border text-muted-foreground hover:text-foreground'
          }`}
        >
          {compareMode ? 'Single Mode' : 'Compare'}
        </button>
      </div>
    </div>
  )
}
