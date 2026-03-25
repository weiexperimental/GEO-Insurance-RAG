'use client'
import { useState, useEffect } from 'react'
import { QueryPanel } from '@/components/query-panel'
import { api } from '@/hooks/use-api'

export default function QueriesPage() {
  const [history, setHistory] = useState<any[]>([])

  useEffect(() => {
    api('/api/queries/history').then(setHistory).catch(() => {})
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-3 text-sm font-semibold">Query Test</h2>
        <QueryPanel />
      </div>
      <div>
        <h2 className="mb-3 text-sm font-semibold">History</h2>
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Query</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Mode</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Time</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {history.map((h, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-card' : ''}>
                  <td className="max-w-md truncate px-3 py-2 font-mono">{h.query}</td>
                  <td className="px-3 py-2 font-mono">{h.mode}</td>
                  <td className="px-3 py-2 font-mono">{h.response_time_ms}ms</td>
                  <td className="px-3 py-2 font-mono text-muted-foreground">{h.timestamp}</td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr><td colSpan={4} className="px-3 py-4 text-center text-muted-foreground">No queries yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
