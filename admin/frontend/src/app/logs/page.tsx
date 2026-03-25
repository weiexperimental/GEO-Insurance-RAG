'use client'
import { useState, useEffect } from 'react'
import { LogViewer } from '@/components/log-viewer'
import { api } from '@/hooks/use-api'
import { useDashboardWs } from '@/hooks/use-dashboard-ws'
import type { LogEntry } from '@/lib/types'

export default function LogsPage() {
  const [dates, setDates] = useState<string[]>([])
  const [selectedDate, setSelectedDate] = useState('')
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [filter, setFilter] = useState('')
  const { logs: wsLogs } = useDashboardWs()

  useEffect(() => {
    api<string[]>('/api/logs/dates').then((d) => {
      setDates(d)
      if (d.length > 0) setSelectedDate(d[0])
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedDate) return
    api<{ entries: LogEntry[] }>(`/api/logs/${selectedDate}`).then((d) => {
      setEntries(d.entries)
    }).catch(() => {})
  }, [selectedDate])

  const today = new Date().toISOString().slice(0, 10)
  const allEntries = selectedDate === today ? [...entries, ...wsLogs] : entries

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold">Logs</h2>
        <select value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)}
          className="rounded border border-border bg-card px-2 py-1 text-xs">
          {dates.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <input type="text" placeholder="Filter..." value={filter} onChange={(e) => setFilter(e.target.value)}
          className="rounded border border-border bg-card px-2 py-1 text-xs" />
      </div>
      <LogViewer entries={allEntries} filter={filter} />
    </div>
  )
}
