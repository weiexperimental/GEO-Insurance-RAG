'use client'
import { useState, useCallback } from 'react'
import { api } from '@/hooks/use-api'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import { EvalQAForm } from '@/components/eval-qa-form'
import type { QAPair } from '@/lib/types'

interface Props {
  pairs: QAPair[]
  total: number
  page: number
  size: number
  onPageChange: (page: number) => void
  onRefresh: () => void
}

const STATUS_BADGE: Record<QAPair['status'], string> = {
  draft: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  approved: 'bg-green-500/15 text-green-400 border-green-500/30',
  rejected: 'bg-red-500/15 text-red-400 border-red-500/30',
}

const CREATED_BY_BADGE: Record<QAPair['created_by'], string> = {
  manual: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  auto_generated: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
}

export function EvalQAList({ pairs, total, page, size, onPageChange, onRefresh }: Props) {
  const { toast } = useToast()
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [editingId, setEditingId] = useState<string | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / size))
  const allChecked = pairs.length > 0 && pairs.every((p) => checkedIds.has(p.id))
  const someChecked = pairs.some((p) => checkedIds.has(p.id)) && !allChecked

  const toggleCheck = useCallback((id: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleAll = useCallback(
    (checked: boolean) => {
      if (checked) setCheckedIds(new Set(pairs.map((p) => p.id)))
      else setCheckedIds(new Set())
    },
    [pairs],
  )

  const handleDelete = useCallback(
    async (id: string) => {
      if (!window.confirm('Delete this QA pair? This cannot be undone.')) return
      try {
        await api(`/api/eval/qa-pairs/${id}`, { method: 'DELETE' })
        toast('QA pair deleted', 'success')
        onRefresh()
      } catch {
        toast('Delete failed', 'error')
      }
    },
    [onRefresh, toast],
  )

  const handleStatusChange = useCallback(
    async (id: string, status: 'approved' | 'rejected') => {
      try {
        await api(`/api/eval/qa-pairs/${id}`, {
          method: 'PUT',
          body: JSON.stringify({ status }),
        })
        toast(`QA pair ${status}`, 'success')
        onRefresh()
      } catch {
        toast('Update failed', 'error')
      }
    },
    [onRefresh, toast],
  )

  const handleBatchStatus = useCallback(
    async (status: 'approved' | 'rejected') => {
      if (checkedIds.size === 0) return
      try {
        await api('/api/eval/qa-pairs/batch-status', {
          method: 'POST',
          body: JSON.stringify({ qa_ids: Array.from(checkedIds), status }),
        })
        toast(`${checkedIds.size} pair${checkedIds.size !== 1 ? 's' : ''} ${status}`, 'success')
        setCheckedIds(new Set())
        onRefresh()
      } catch {
        toast('Batch update failed', 'error')
      }
    },
    [checkedIds, onRefresh, toast],
  )

  const handleEditSave = useCallback(
    async (data: {
      question: string
      expected_answer: string
      source_doc: string
      category: string
      difficulty: string
    }) => {
      if (!editingId) return
      await api(`/api/eval/qa-pairs/${editingId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      })
      toast('QA pair updated', 'success')
      setEditingId(null)
      onRefresh()
    },
    [editingId, onRefresh, toast],
  )

  return (
    <div className="flex flex-col gap-0">
      {/* Header row */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <input
          type="checkbox"
          checked={allChecked}
          ref={(el) => {
            if (el) el.indeterminate = someChecked
          }}
          onChange={(e) => toggleAll(e.target.checked)}
          className="size-3.5 accent-indigo-500"
        />
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {total} pair{total !== 1 ? 's' : ''}
        </span>

        {/* Bulk actions */}
        {checkedIds.size > 0 && (
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-[10px] text-muted-foreground">
              {checkedIds.size} selected
            </span>
            <Button
              size="xs"
              variant="outline"
              onClick={() => handleBatchStatus('approved')}
              className="border-green-500/40 text-green-400 hover:bg-green-500/10"
            >
              Approve All
            </Button>
            <Button
              size="xs"
              variant="outline"
              onClick={() => handleBatchStatus('rejected')}
              className="border-red-500/40 text-red-400 hover:bg-red-500/10"
            >
              Reject All
            </Button>
          </div>
        )}
      </div>

      {/* Pair rows */}
      <div className="flex-1 overflow-y-auto">
        {pairs.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
            No QA pairs found
          </div>
        ) : (
          pairs.map((pair) => (
            <div key={pair.id} className="border-b border-border">
              <div className="flex gap-2 px-3 py-3 hover:bg-muted/20 transition-colors">
                {/* Checkbox */}
                <div className="mt-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={checkedIds.has(pair.id)}
                    onChange={() => toggleCheck(pair.id)}
                    className="size-3.5 accent-indigo-500"
                  />
                </div>

                {/* Content */}
                <div className="min-w-0 flex-1 flex flex-col gap-1.5">
                  {/* Question */}
                  <div className="text-xs font-medium text-foreground">
                    Q: {pair.question}
                  </div>

                  {/* Answer */}
                  <div className="text-xs text-foreground/70">
                    A: {pair.expected_answer}
                  </div>

                  {/* Tags row */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {pair.difficulty}
                    </span>
                    <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {pair.category}
                    </span>
                    {pair.source_doc && (
                      <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground truncate max-w-[200px]">
                        {pair.source_doc}
                      </span>
                    )}
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${STATUS_BADGE[pair.status]}`}
                    >
                      {pair.status}
                    </span>
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${CREATED_BY_BADGE[pair.created_by]}`}
                    >
                      {pair.created_by === 'auto_generated' ? 'auto' : 'manual'}
                    </span>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-1.5 flex-wrap">
                    {pair.status === 'draft' && (
                      <>
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => handleStatusChange(pair.id, 'approved')}
                          className="border-green-500/40 text-green-400 hover:bg-green-500/10"
                        >
                          Approve
                        </Button>
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => handleStatusChange(pair.id, 'rejected')}
                          className="border-red-500/40 text-red-400 hover:bg-red-500/10"
                        >
                          Reject
                        </Button>
                      </>
                    )}
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => setEditingId(editingId === pair.id ? null : pair.id)}
                    >
                      Edit
                    </Button>
                    <Button
                      size="xs"
                      variant="destructive"
                      onClick={() => handleDelete(pair.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </div>

              {/* Inline edit form */}
              {editingId === pair.id && (
                <div className="px-3 pb-3">
                  <EvalQAForm
                    pair={pair}
                    onSave={handleEditSave}
                    onCancel={() => setEditingId(null)}
                  />
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 border-t border-border px-3 py-2">
          <Button
            size="xs"
            variant="outline"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            ‹
          </Button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            let p: number
            if (totalPages <= 7) {
              p = i + 1
            } else if (page <= 4) {
              p = i + 1
            } else if (page >= totalPages - 3) {
              p = totalPages - 6 + i
            } else {
              p = page - 3 + i
            }
            return (
              <Button
                key={p}
                size="xs"
                variant={p === page ? 'default' : 'outline'}
                onClick={() => onPageChange(p)}
              >
                {p}
              </Button>
            )
          })}
          <Button
            size="xs"
            variant="outline"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            ›
          </Button>
        </div>
      )}
    </div>
  )
}
