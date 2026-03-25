interface StatsCardProps {
  label: string
  value: string | number
  color?: string
}

export function StatsCard({ label, value, color }: StatsCardProps) {
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className={`font-mono text-2xl font-bold ${color || 'text-foreground'}`}>
        {value ?? '—'}
      </div>
    </div>
  )
}
