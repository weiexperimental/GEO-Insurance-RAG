'use client'
import { useState } from 'react'
import { api } from '@/hooks/use-api'
import { Button } from '@/components/ui/button'
import { EvalRunDetail } from '@/components/eval-run-detail'
import type { EvalRun, EvalScores } from '@/lib/types'

interface Props {
  runs: EvalRun[]
  onRunEval: () => void
  running: boolean
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'text-green-400'
  if (score >= 0.6) return 'text-yellow-400'
  return 'text-red-400'
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round(score * 100)
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] text-muted-foreground w-16 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full ${score >= 0.8 ? 'bg-green-500' : score >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-[10px] font-medium w-8 text-right ${scoreColor(score)}`}>{pct}%</span>
    </div>
  )
}

function trendArrow(current: EvalScores, prev: EvalScores): string {
  const currentAvg =
    (current.answer_correctness + current.faithfulness + current.context_relevancy) / 3
  const prevAvg = (prev.answer_correctness + prev.faithfulness + prev.context_relevancy) / 3
  if (currentAvg > prevAvg + 0.005) return '↑'
  if (currentAvg < prevAvg - 0.005) return '↓'
  return '→'
}

function trendColor(current: EvalScores, prev: EvalScores): string {
  const currentAvg =
    (current.answer_correctness + current.faithfulness + current.context_relevancy) / 3
  const prevAvg = (prev.answer_correctness + prev.faithfulness + prev.context_relevancy) / 3
  if (currentAvg > prevAvg + 0.005) return 'text-green-400'
  if (currentAvg < prevAvg - 0.005) return 'text-red-400'
  return 'text-muted-foreground'
}

const STATUS_BADGE: Record<EvalRun['status'], string> = {
  running: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  completed: 'bg-green-500/15 text-green-400 border-green-500/30',
  failed: 'bg-red-500/15 text-red-400 border-red-500/30',
}

export function EvalRunsList({ runs, onRunEval, running }: Props) {
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)
  const [detailResults, setDetailResults] = useState<Record<string, EvalRun>>({})
  const [loadingDetail, setLoadingDetail] = useState<string | null>(null)

  const handleViewDetail = async (runId: string) => {
    if (expandedRunId === runId) {
      setExpandedRunId(null)
      return
    }
    setExpandedRunId(runId)
    if (detailResults[runId]) return
    setLoadingDetail(runId)
    try {
      const detail = await api<EvalRun>(`/api/eval/runs/${runId}`)
      setDetailResults((prev) => ({ ...prev, [runId]: detail }))
    } catch {
      // ignore
    } finally {
      setLoadingDetail(null)
    }
  }

  const sortedRuns = [...runs].sort((a, b) => b.timestamp - a.timestamp)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {runs.length} run{runs.length !== 1 ? 's' : ''}
        </span>
        <Button size="xs" variant="default" onClick={onRunEval} disabled={running}>
          {running ? 'Running…' : 'Run Evaluation'}
        </Button>
      </div>

      {sortedRuns.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
          No evaluation runs yet. Click "Run Evaluation" to start.
        </div>
      ) : (
        sortedRuns.map((run, idx) => {
          const prevRun = sortedRuns[idx + 1]
          const isExpanded = expandedRunId === run.run_id
          const detail = detailResults[run.run_id]
          const ts = new Date(run.timestamp * 1000)
          const tsStr = ts.toLocaleString('en-HK', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })
          return (
            <div
              key={run.run_id}
              className="rounded-md border border-border bg-card overflow-hidden"
            >
              <div className="flex flex-col gap-3 px-4 py-3">
                {/* Header row */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-mono text-xs text-foreground truncate">
                      {run.run_id}
                    </span>
                    {prevRun && (
                      <span
                        className={`text-sm font-bold ${trendColor(run.scores, prevRun.scores)}`}
                        title="vs previous run"
                      >
                        {trendArrow(run.scores, prevRun.scores)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] text-muted-foreground">{tsStr}</span>
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${STATUS_BADGE[run.status]}`}
                    >
                      {run.status}
                    </span>
                  </div>
                </div>

                {/* Score bars */}
                <div className="flex flex-col gap-1.5">
                  <ScoreBar label="Correctness" score={run.scores.answer_correctness} />
                  <ScoreBar label="Faithfulness" score={run.scores.faithfulness} />
                  <ScoreBar label="Relevancy" score={run.scores.context_relevancy} />
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">
                    {run.total_pairs} pairs evaluated
                  </span>
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => handleViewDetail(run.run_id)}
                    disabled={loadingDetail === run.run_id}
                  >
                    {loadingDetail === run.run_id
                      ? 'Loading…'
                      : isExpanded
                        ? 'Hide Details'
                        : 'View Details'}
                  </Button>
                </div>
              </div>

              {/* Detail panel */}
              {isExpanded && (
                <div className="border-t border-border">
                  {detail ? (
                    <EvalRunDetail results={detail.results ?? []} />
                  ) : loadingDetail === run.run_id ? (
                    <div className="flex items-center justify-center py-6 text-xs text-muted-foreground">
                      Loading…
                    </div>
                  ) : (
                    <div className="flex items-center justify-center py-6 text-xs text-muted-foreground">
                      No details available
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}
