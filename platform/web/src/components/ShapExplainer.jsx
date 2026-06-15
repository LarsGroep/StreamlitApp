export default function ShapExplainer({ features }) {
  if (!features?.length) return null

  const maxAbs = Math.max(...features.map(f => Math.abs(f.shap_value)), 0.001)

  return (
    <div className="space-y-1.5">
      {features.map(f => {
        const pct    = Math.abs(f.shap_value) / maxAbs * 100
        const pos    = f.shap_value >= 0
        return (
          <div key={f.feature} className="flex items-center gap-3 text-xs">
            <span className="w-44 truncate text-lofi-muted text-right shrink-0">{f.feature}</span>
            <div className="flex-1 flex items-center gap-1">
              <div className="flex-1 flex justify-end">
                {!pos && (
                  <div
                    className="h-2 rounded-sm bg-red-500/70"
                    style={{ width: `${pct}%` }}
                  />
                )}
              </div>
              <div className="w-px h-3 bg-lofi-border" />
              <div className="flex-1">
                {pos && (
                  <div
                    className="h-2 rounded-sm bg-lofi-accent/80"
                    style={{ width: `${pct}%` }}
                  />
                )}
              </div>
            </div>
            <span className={`w-14 text-right ${pos ? 'text-lofi-accent' : 'text-red-400'}`}>
              {f.shap_value >= 0 ? '+' : ''}{f.shap_value.toFixed(3)}
            </span>
          </div>
        )
      })}
      <div className="flex justify-between text-xs text-lofi-muted pt-1 border-t border-lofi-border">
        <span>← decreases score</span>
        <span>increases score →</span>
      </div>
    </div>
  )
}
