export default function ScoreBar({ label, value, max = 100, accent = false }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-lofi-muted">
        <span>{label}</span>
        <span className={accent ? 'text-lofi-accent font-bold' : ''}>{value?.toFixed(1)}</span>
      </div>
      <div className="h-1.5 bg-lofi-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${accent ? 'bg-lofi-accent' : 'bg-white/30'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
