'use client'
import { useEffect, useState } from 'react'
import useWebSocket from 'react-use-websocket'
import type { SystemHealth, IngestionStatus, LogEntry, WsMessage } from '@/lib/types'

// In production (behind Caddy proxy), derive WS URL from current page location.
// In development, fall back to localhost:8080.
function getWsUrl(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/ws`
  }
  return 'ws://localhost:8080/ws'
}
const WS_URL = getWsUrl()

export function useDashboardWs() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null)
  const [ingestion, setIngestion] = useState<IngestionStatus | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])

  const { lastJsonMessage, readyState } = useWebSocket(WS_URL, {
    shouldReconnect: () => true,
    reconnectAttempts: Infinity,
    reconnectInterval: (attempt: number) => Math.min(1000 * 2 ** attempt, 30000),
  })

  useEffect(() => {
    if (!lastJsonMessage) return
    const msg = lastJsonMessage as WsMessage

    switch (msg.type) {
      case 'system_health':
        setSystemHealth(msg.data)
        break
      case 'ingestion_update':
        setIngestion(msg.data)
        break
      case 'log_entry':
        setLogs(prev => [...prev.slice(-999), msg.data])
        break
      case 'snapshot':
        if (msg.data.system_health) setSystemHealth(msg.data.system_health)
        if (msg.data.ingestion) setIngestion(msg.data.ingestion)
        break
    }
  }, [lastJsonMessage])

  return { systemHealth, ingestion, logs, readyState }
}
