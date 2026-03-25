'use client'
import { useState, useCallback, useRef } from 'react'
import { api } from '@/hooks/use-api'
import type { PlaygroundQueryRequest, PlaygroundResult, PlaygroundCompareResult } from '@/lib/types'
import { PlaygroundQueryBar } from '@/components/playground-query-bar'
import { PlaygroundResultPanel } from '@/components/playground-result-panel'
import { PlaygroundCompareView } from '@/components/playground-compare-view'

export default function PlaygroundPage() {
  const [singleResult, setSingleResult] = useState<PlaygroundResult | null>(null)
  const [compareResult, setCompareResult] = useState<PlaygroundCompareResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const runQuery = useCallback(async (path: string, body: object) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    try {
      const result = await api<any>(path, {
        method: 'POST',
        body: JSON.stringify(body),
        signal: controller.signal,
      })
      return result
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        setError(e instanceof Error ? e.message : 'Request failed')
      }
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const handleRun = useCallback(async (params: PlaygroundQueryRequest) => {
    setCompareResult(null)
    const result = await runQuery('/api/playground/query', params)
    if (result) setSingleResult(result)
  }, [runQuery])

  const handleRetrieveOnly = useCallback(async (params: PlaygroundQueryRequest) => {
    setCompareResult(null)
    const result = await runQuery('/api/playground/retrieve-only', params)
    if (result) setSingleResult(result)
  }, [runQuery])

  const handleCompare = useCallback(async (
    query: string,
    paramsA: Omit<PlaygroundQueryRequest, 'query'>,
    paramsB: Omit<PlaygroundQueryRequest, 'query'>,
  ) => {
    setSingleResult(null)
    const result = await runQuery('/api/playground/compare', {
      query, params_a: paramsA, params_b: paramsB,
    })
    if (result) setCompareResult(result)
  }, [runQuery])

  return (
    <div className="flex flex-col gap-4">
      <PlaygroundQueryBar
        onRun={handleRun}
        onRetrieveOnly={handleRetrieveOnly}
        onCompare={handleCompare}
        loading={loading}
      />

      {error && (
        <div className="rounded border border-destructive/50 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      {loading && !singleResult && !compareResult && (
        <div className="flex items-center justify-center py-20 text-xs text-muted-foreground">
          Running query...
        </div>
      )}

      {compareResult && <PlaygroundCompareView result={compareResult} />}

      {singleResult && !compareResult && (
        <div className="rounded-md border border-border bg-card p-4">
          <PlaygroundResultPanel result={singleResult} />
        </div>
      )}

      {!singleResult && !compareResult && !loading && !error && (
        <div className="flex items-center justify-center py-20 text-xs text-muted-foreground">
          Enter a query and click Run to test the RAG pipeline
        </div>
      )}
    </div>
  )
}
