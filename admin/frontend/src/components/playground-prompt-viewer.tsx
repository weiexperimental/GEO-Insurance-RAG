'use client'
import { useState } from 'react'

interface Props {
  prompt: string | null
}

export function PlaygroundPromptViewer({ prompt }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!prompt) return null

  return (
    <div className="rounded border border-border bg-background">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
      >
        <span className="text-[10px]">{expanded ? '▾' : '▸'}</span>
        Full Prompt ({prompt.length.toLocaleString()} chars)
      </button>
      {expanded && (
        <pre className="max-h-96 overflow-auto border-t border-border px-3 py-2 text-[11px] text-foreground whitespace-pre-wrap leading-relaxed">
          {prompt}
        </pre>
      )}
    </div>
  )
}
