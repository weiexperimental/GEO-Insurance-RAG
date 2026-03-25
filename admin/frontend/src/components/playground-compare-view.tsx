import type { PlaygroundCompareResult } from '@/lib/types'
import { PlaygroundResultPanel } from './playground-result-panel'

interface Props {
  result: PlaygroundCompareResult
}

export function PlaygroundCompareView({ result }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <PlaygroundResultPanel result={result.result_a} label="Result A" />
      <PlaygroundResultPanel result={result.result_b} label="Result B" />
    </div>
  )
}
