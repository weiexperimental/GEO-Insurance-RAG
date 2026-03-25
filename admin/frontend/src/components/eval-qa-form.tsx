'use client'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { QAPair } from '@/lib/types'

interface Props {
  pair?: QAPair
  onSave: (data: {
    question: string
    expected_answer: string
    source_doc: string
    category: string
    difficulty: string
  }) => Promise<void>
  onCancel: () => void
}

const CATEGORIES = ['product_detail', 'pricing', 'eligibility', 'claims', 'coverage', 'general']
const DIFFICULTIES = ['simple', 'medium', 'complex']

export function EvalQAForm({ pair, onSave, onCancel }: Props) {
  const [question, setQuestion] = useState(pair?.question ?? '')
  const [expectedAnswer, setExpectedAnswer] = useState(pair?.expected_answer ?? '')
  const [sourceDoc, setSourceDoc] = useState(pair?.source_doc ?? '')
  const [category, setCategory] = useState(pair?.category ?? 'general')
  const [difficulty, setDifficulty] = useState(pair?.difficulty ?? 'simple')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || !expectedAnswer.trim()) {
      setError('Question and expected answer are required')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSave({ question, expected_answer: expectedAnswer, source_doc: sourceDoc, category, difficulty })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const inputCls =
    'w-full rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring'
  const selectCls =
    'rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring'

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-md border border-border bg-card p-4 flex flex-col gap-3"
    >
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {pair ? 'Edit QA Pair' : 'New QA Pair'}
      </div>

      {error && (
        <div className="rounded border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-1">
        <label className="text-[10px] text-muted-foreground">Question</label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="Enter question..."
          className={inputCls}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[10px] text-muted-foreground">Expected Answer</label>
        <textarea
          value={expectedAnswer}
          onChange={(e) => setExpectedAnswer(e.target.value)}
          rows={3}
          placeholder="Enter expected answer..."
          className={inputCls}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[10px] text-muted-foreground">Source Document</label>
        <input
          type="text"
          value={sourceDoc}
          onChange={(e) => setSourceDoc(e.target.value)}
          placeholder="e.g. AXA_危疾保障_2026"
          className={inputCls}
        />
      </div>

      <div className="flex gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-muted-foreground">Category</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)} className={selectCls}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-muted-foreground">Difficulty</label>
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className={selectCls}>
            {DIFFICULTIES.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-2 border-t border-border pt-3">
        <Button size="xs" variant="default" type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
        <Button size="xs" variant="outline" type="button" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
