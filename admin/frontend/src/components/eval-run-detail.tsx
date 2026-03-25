'use client'
import { useState } from 'react'
import type { EvalResultItem } from '@/lib/types'

interface Props {
  results: EvalResultItem[]
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'text-green-400'
  if (score >= 0.6) return 'text-yellow-400'
  return 'text-red-400'
}

function scoreBg(score: number): string {
  if (score >= 0.8) return 'bg-green-500/15 border-green-500/30'
  if (score >= 0.6) return 'bg-yellow-500/15 border-yellow-500/30'
  return 'bg-red-500/15 border-red-500/30'
}

function ScoreCell({ score }: { score: number }) {
  return (
    <span
      className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium ${scoreColor(score)} ${scoreBg(score)}`}
    >
      {(score * 100).toFixed(0)}%
    </span>
  )
}

export function EvalRunDetail({ results }: Props) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (results.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
        No results available
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-0 overflow-x-auto">
      {/* Header */}
      <div className="grid grid-cols-[1fr_1fr_1fr_60px_60px_60px] gap-2 border-b border-border px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground">
        <span>Question</span>
        <span>Expected</span>
        <span>Actual</span>
        <span>Correct</span>
        <span>Faith</span>
        <span>Relev</span>
      </div>

      {results.map((item) => {
        const isExpanded = expandedIds.has(item.qa_pair_id)
        const truncated = item.actual_response.length > 80
        return (
          <div
            key={item.qa_pair_id}
            className="grid grid-cols-[1fr_1fr_1fr_60px_60px_60px] gap-2 border-b border-border px-3 py-2 hover:bg-muted/30 transition-colors"
          >
            <div className="text-xs text-foreground leading-relaxed">{item.question}</div>
            <div className="text-xs text-foreground/70 leading-relaxed">{item.expected_answer}</div>
            <div
              className="text-xs text-foreground/70 leading-relaxed cursor-pointer"
              onClick={() => toggleExpand(item.qa_pair_id)}
              title={truncated && !isExpanded ? 'Click to expand' : undefined}
            >
              {isExpanded || !truncated
                ? item.actual_response
                : `${item.actual_response.slice(0, 80)}…`}
              {truncated && (
                <span className="ml-1 text-[10px] text-muted-foreground">
                  {isExpanded ? '(collapse)' : '(expand)'}
                </span>
              )}
            </div>
            <div className="flex items-start pt-0.5">
              <ScoreCell score={item.scores.answer_correctness} />
            </div>
            <div className="flex items-start pt-0.5">
              <ScoreCell score={item.scores.faithfulness} />
            </div>
            <div className="flex items-start pt-0.5">
              <ScoreCell score={item.scores.context_relevancy} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
