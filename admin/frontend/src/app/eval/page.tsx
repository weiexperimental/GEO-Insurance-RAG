'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/hooks/use-api'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import { EvalQAList } from '@/components/eval-qa-list'
import { EvalQAForm } from '@/components/eval-qa-form'
import { EvalGenerateModal } from '@/components/eval-generate-modal'
import { EvalRunsList } from '@/components/eval-runs-list'
import type { QAPairsResponse, EvalRun } from '@/lib/types'

type Tab = 'qa' | 'runs'

const PAGE_SIZE = 20

interface QAFilters {
  status: string
  category: string
  search: string
}

export default function EvalPage() {
  const { toast } = useToast()
  const [tab, setTab] = useState<Tab>('qa')

  // QA Pairs state
  const [filters, setFilters] = useState<QAFilters>({ status: '', category: '', search: '' })
  const [pairs, setPairs] = useState<QAPairsResponse | null>(null)
  const [qaPage, setQAPage] = useState(1)
  const [qaLoading, setQALoading] = useState(false)
  const [qaError, setQAError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [showGenerateModal, setShowGenerateModal] = useState(false)

  const filtersRef = useRef(filters)
  const qaPageRef = useRef(qaPage)

  // Eval runs state
  const [runs, setRuns] = useState<EvalRun[]>([])
  const [runsLoading, setRunsLoading] = useState(false)
  const [runsError, setRunsError] = useState<string | null>(null)
  const [evalRunning, setEvalRunning] = useState(false)

  // ─── QA Pairs ───────────────────────────────────────────────────────────────

  const fetchQAPairs = useCallback(async (f: QAFilters, p: number) => {
    setQALoading(true)
    setQAError(null)
    try {
      const params = new URLSearchParams()
      if (f.status) params.set('status', f.status)
      if (f.category) params.set('category', f.category)
      if (f.search) params.set('search', f.search)
      params.set('page', String(p))
      params.set('size', String(PAGE_SIZE))
      const result = await api<QAPairsResponse>(`/api/eval/qa-pairs?${params.toString()}`)
      setPairs(result)
    } catch (e) {
      setQAError(e instanceof Error ? e.message : 'Failed to load QA pairs')
    } finally {
      setQALoading(false)
    }
  }, [])

  useEffect(() => {
    fetchQAPairs(filters, qaPage)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleFilterChange = useCallback(
    (key: keyof QAFilters, value: string) => {
      const newFilters = { ...filtersRef.current, [key]: value }
      filtersRef.current = newFilters
      qaPageRef.current = 1
      setFilters(newFilters)
      setQAPage(1)
      fetchQAPairs(newFilters, 1)
    },
    [fetchQAPairs],
  )

  const handleQAPageChange = useCallback(
    (p: number) => {
      qaPageRef.current = p
      setQAPage(p)
      fetchQAPairs(filtersRef.current, p)
    },
    [fetchQAPairs],
  )

  const handleRefresh = useCallback(() => {
    fetchQAPairs(filtersRef.current, qaPageRef.current)
  }, [fetchQAPairs])

  const handleAddSave = useCallback(
    async (data: {
      question: string
      expected_answer: string
      source_doc: string
      category: string
      difficulty: string
    }) => {
      await api('/api/eval/qa-pairs', {
        method: 'POST',
        body: JSON.stringify(data),
      })
      toast('QA pair created', 'success')
      setShowAddForm(false)
      handleRefresh()
    },
    [handleRefresh, toast],
  )

  // ─── Eval Runs ───────────────────────────────────────────────────────────────

  const fetchRuns = useCallback(async () => {
    setRunsLoading(true)
    setRunsError(null)
    try {
      const result = await api<{ runs: EvalRun[] }>('/api/eval/runs')
      setRuns(result.runs ?? [])
    } catch (e) {
      setRunsError(e instanceof Error ? e.message : 'Failed to load runs')
    } finally {
      setRunsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tab === 'runs') {
      fetchRuns()
    }
  }, [tab, fetchRuns])

  const handleRunEval = useCallback(async () => {
    setEvalRunning(true)
    try {
      await api('/api/eval/run', { method: 'POST' })
      toast('Evaluation started', 'success')
      fetchRuns()
    } catch (e) {
      toast('Failed to start evaluation', 'error')
    } finally {
      setEvalRunning(false)
    }
  }, [fetchRuns, toast])

  const selectCls =
    'rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring'

  return (
    <div className="flex flex-col gap-3 h-[calc(100vh-80px)]">
      {/* Tabs */}
      <div className="flex items-center gap-1 rounded-md border border-border bg-card px-3 py-2">
        <Button
          size="xs"
          variant={tab === 'qa' ? 'default' : 'ghost'}
          onClick={() => setTab('qa')}
        >
          QA Pairs
        </Button>
        <Button
          size="xs"
          variant={tab === 'runs' ? 'default' : 'ghost'}
          onClick={() => setTab('runs')}
        >
          Eval Runs
        </Button>
      </div>

      {/* QA Pairs Tab */}
      {tab === 'qa' && (
        <div className="flex flex-1 flex-col overflow-hidden rounded-md border border-border bg-card">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2 shrink-0">
            <Button size="xs" variant="outline" onClick={() => setShowAddForm((v) => !v)}>
              {showAddForm ? '✕ Cancel' : '+ Add QA Pair'}
            </Button>
            <Button size="xs" variant="outline" onClick={() => setShowGenerateModal(true)}>
              Generate…
            </Button>

            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className={selectCls}
            >
              <option value="">Status: All</option>
              <option value="draft">Draft</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>

            <select
              value={filters.category}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              className={selectCls}
            >
              <option value="">Category: All</option>
              <option value="product_detail">Product Detail</option>
              <option value="pricing">Pricing</option>
              <option value="eligibility">Eligibility</option>
              <option value="claims">Claims</option>
              <option value="coverage">Coverage</option>
              <option value="general">General</option>
            </select>

            <input
              type="text"
              placeholder="Search…"
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              className="w-40 rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          {/* Add form */}
          {showAddForm && (
            <div className="border-b border-border px-3 py-3 shrink-0">
              <EvalQAForm onSave={handleAddSave} onCancel={() => setShowAddForm(false)} />
            </div>
          )}

          {/* Error */}
          {qaError && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive mx-3 my-2">
              {qaError}
            </div>
          )}

          {/* List */}
          <div className="flex-1 overflow-y-auto">
            {qaLoading ? (
              <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
                Loading…
              </div>
            ) : pairs ? (
              <EvalQAList
                pairs={pairs.pairs}
                total={pairs.total}
                page={qaPage}
                size={PAGE_SIZE}
                onPageChange={handleQAPageChange}
                onRefresh={handleRefresh}
              />
            ) : null}
          </div>
        </div>
      )}

      {/* Eval Runs Tab */}
      {tab === 'runs' && (
        <div className="flex-1 overflow-y-auto rounded-md border border-border bg-card px-4 py-4">
          {runsError && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive mb-3">
              {runsError}
            </div>
          )}
          {runsLoading ? (
            <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
              Loading…
            </div>
          ) : (
            <EvalRunsList runs={runs} onRunEval={handleRunEval} running={evalRunning} />
          )}
        </div>
      )}

      {/* Generate modal */}
      {showGenerateModal && (
        <EvalGenerateModal
          onClose={() => setShowGenerateModal(false)}
          onGenerated={handleRefresh}
        />
      )}
    </div>
  )
}
