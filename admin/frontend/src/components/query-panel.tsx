'use client'
import { useState } from 'react'
import { api } from '@/hooks/use-api'

const modes = ['hybrid', 'local', 'global', 'naive', 'mix', 'bypass']

export function QueryPanel() {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('hybrid')
  const [response, setResponse] = useState('')
  const [responseTime, setResponseTime] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!query.trim()) return
    setLoading(true)
    setResponse('')
    try {
      const result = await api<{ response: string; response_time_ms: number }>('/api/queries', {
        method: 'POST',
        body: JSON.stringify({ query, mode }),
      })
      setResponse(result.response)
      setResponseTime(result.response_time_ms)
    } catch (e: any) {
      setResponse(`Error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input type="text" placeholder="Enter a query..." value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          className="flex-1 rounded border border-border bg-card px-3 py-1.5 text-xs" />
        <select value={mode} onChange={(e) => setMode(e.target.value)}
          className="rounded border border-border bg-card px-2 py-1 text-xs">
          {modes.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <button onClick={handleSubmit} disabled={loading}
          className="rounded bg-white px-3 py-1.5 text-xs font-medium text-black disabled:opacity-50">
          {loading ? 'Querying...' : 'Query'}
        </button>
      </div>
      {response && (
        <div className="rounded-md border border-border bg-card p-4">
          {responseTime !== null && (
            <div className="mb-2 font-mono text-[10px] text-muted-foreground">{responseTime}ms · {mode}</div>
          )}
          <div className="whitespace-pre-wrap text-xs">{response}</div>
        </div>
      )}
    </div>
  )
}
