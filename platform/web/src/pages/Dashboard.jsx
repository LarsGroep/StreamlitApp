import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMomentum } from '../api/client'

function DeltaBadge({ delta }) {
  if (delta === 0) return <span className="text-lofi-muted text-xs">—</span>
  const pos = delta > 0
  return (
    <span className={`text-xs font-mono ${pos ? 'text-lofi-accent' : 'text-red-400'}`}>
      {pos ? '+' : ''}{delta.toFixed(1)}
    </span>
  )
}

export default function Dashboard() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [topN, setTopN]     = useState(50)

  useEffect(() => {
    setLoading(true)
    getMomentum({ top_n: topN })
      .then(r => setData(r.data))
      .finally(() => setLoading(false))
  }, [topN])

  return (
    <div>
      <div className="flex items-baseline justify-between mb-6">
        <h1 className="text-xl font-bold">Momentum Dashboard</h1>
        {data && (
          <span className="text-xs text-lofi-muted">
            {new Date(data.as_of).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>

      {loading && <p className="text-lofi-muted text-sm">Loading…</p>}

      {data && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-lofi-muted text-xs border-b border-lofi-border">
              <th className="pb-2 font-normal">Artist</th>
              <th className="pb-2 font-normal text-right">Growth</th>
              <th className="pb-2 font-normal text-right">30d Δ</th>
              <th className="pb-2 font-normal text-right">Momentum</th>
              <th className="pb-2 font-normal text-center">LOFI</th>
            </tr>
          </thead>
          <tbody>
            {data.top_movers.map((a, i) => (
              <tr key={a.id} className="border-b border-lofi-border/50 hover:bg-lofi-surface/50 transition-colors">
                <td className="py-2.5">
                  <Link to={`/artists/${a.id}`} className="hover:text-lofi-accent transition-colors">
                    <span className="text-lofi-muted text-xs mr-2">{i + 1}</span>
                    {a.name}
                  </Link>
                </td>
                <td className="py-2.5 text-right font-mono text-xs">{a.growth_score_now.toFixed(1)}</td>
                <td className="py-2.5 text-right"><DeltaBadge delta={a.growth_delta} /></td>
                <td className="py-2.5 text-right font-mono text-xs">{a.momentum_score.toFixed(1)}</td>
                <td className="py-2.5 text-center">
                  {a.lofi_booked ? <span className="text-lofi-accent text-xs">●</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
