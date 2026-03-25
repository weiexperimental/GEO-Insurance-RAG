'use client'
import { useEffect, useRef } from 'react'
import type { LogEntry } from '@/lib/types'

function formatEntry(entry: LogEntry): string {
  if (entry.raw) return entry.raw
  const ts = entry.timestamp?.slice(11, 19) || ''
  const status = entry.status === 'success' ? '✓' : entry.status === 'failed' ? '✗' : '▶'
  return `${ts} ${status} ${entry.document || ''} · ${entry.stage || ''} · ${entry.duration_ms ?? 0}ms`
}

interface Props {
  entries: LogEntry[]
  filter: string
}

export function LogViewer({ entries, filter }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  const filtered = filter
    ? entries.filter((e) => JSON.stringify(e).toLowerCase().includes(filter.toLowerCase()))
    : entries

  return (
    <div className="h-[500px] overflow-y-auto rounded-md border border-border bg-black p-3 font-mono text-xs">
      {filtered.map((entry, i) => {
        const line = formatEntry(entry)
        const color = entry.status === 'failed' ? 'text-[hsl(var(--error))]'
          : entry.status === 'success' ? 'text-[hsl(var(--success))]'
          : 'text-muted-foreground'
        return <div key={i} className={`leading-6 ${color}`}>{line}</div>
      })}
      <div ref={bottomRef} />
    </div>
  )
}
