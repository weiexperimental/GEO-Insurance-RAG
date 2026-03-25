'use client'
import { useEffect, useState } from 'react'
import { api } from '@/hooks/use-api'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import type { Document } from '@/lib/types'

interface Props {
  onClose: () => void
  onGenerated: () => void
}

export function EvalGenerateModal({ onClose, onGenerated }: Props) {
  const { toast } = useToast()
  const [docs, setDocs] = useState<Document[]>([])
  const [docId, setDocId] = useState('')
  const [count, setCount] = useState(10)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    api<{ documents: Document[] }>('/api/documents?limit=200&offset=0')
      .then((d) => setDocs(d.documents))
      .catch(() => {})
  }, [])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const body: { count: number; doc_id?: string } = { count }
      if (docId) body.doc_id = docId
      const result = await api<{ generated: number }>('/api/eval/generate', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      toast(`Generated ${result.generated ?? count} QA pair${count !== 1 ? 's' : ''}`, 'success')
      onGenerated()
      onClose()
    } catch (e) {
      toast('Generate failed', 'error')
    } finally {
      setGenerating(false)
    }
  }

  const selectCls =
    'w-full rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-96 rounded-md border border-border bg-card p-5 flex flex-col gap-4 shadow-xl">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-foreground">Generate QA Pairs</span>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors text-xs"
          >
            ✕
          </button>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-muted-foreground">Document (optional)</label>
          <select value={docId} onChange={(e) => setDocId(e.target.value)} className={selectCls}>
            <option value="">All Documents</option>
            {docs.map((d) => (
              <option key={d.document_id} value={d.document_id}>
                {d.file_name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-muted-foreground">Count</label>
          <input
            type="number"
            value={count}
            min={1}
            max={100}
            onChange={(e) => setCount(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-full rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        <div className="flex gap-2 border-t border-border pt-3">
          <Button size="xs" variant="default" onClick={handleGenerate} disabled={generating}>
            {generating ? 'Generating…' : 'Generate'}
          </Button>
          <Button size="xs" variant="outline" onClick={onClose} disabled={generating}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  )
}
