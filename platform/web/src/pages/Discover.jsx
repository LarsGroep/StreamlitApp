import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { discoverLofi } from '../api/client'

function SimilarityBadge({ score }) {
  const color = score >= 75 ? 'text-lofi-accent' : score >= 50 ? 'text-white/80' : 'text-lofi-muted'
  return (
    <span className={`font-mono font-bold text-sm ${color}`}>
      {score.toFixed(0)}
    </span>
  )
}

function ListenersBadge({ value }) {
  if (!value) return <span className="text-lofi-muted text-xs">—</span>
  if (value < 1000) return <span className="text-xs text-lofi-muted">{value.toFixed(0)}</span>
  return <span className="text-xs text-lofi-muted">{(value / 1000).toFixed(0)}k</span>
}

export default function Discover() {
  const [results, setResults]       = useState(null)
  const [loading, setLoading]       = useState(false)
  const [threshold, setThreshold]   = useState(100000)
  const [minSim, setMinSim]         = useState(0)
  const [minGrowth, setMinGrowth]   = useState(0)

  function load() {
    setLoading(true)
    discoverLofi({
      listener_threshold: threshold,
      min_similarity: minSim,
      min_growth: minGrowth,
      top_n: 100,
    })
      .then(r => setResults(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold">Discover</h1>
        <p className="text-xs text-lofi-muted mt-1">
          Artists with LOFI sound characteristics not yet on the wider market's radar.
          Ranked by similarity to the LOFI-booked artist cluster.
        </p>
      </div>

      {/* Filters */}
      <form
        onSubmit={e => { e.preventDefault(); load() }}
        className="flex flex-wrap gap-3 mb-8"
      >
        <div className="flex flex-col gap-1">
          <label className="text-xs text-lofi-muted">Max Spotify listeners</label>
          <input
            type="number" value={threshold} step={10000} min={1000}
            onChange={e => setThreshold(Number(e.target.value))}
            className="bg-lofi-surface border border-lofi-border rounded px-3 py-2 text-sm w-44 focus:outline-none focus:border-white/40"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-lofi-muted">Min LOFI similarity</label>
          <input
            type="number" value={minSim} step={5} min={0} max={100}
            onChange={e => setMinSim(Number(e.target.value))}
            className="bg-lofi-surface border border-lofi-border rounded px-3 py-2 text-sm w-36 focus:outline-none focus:border-white/40"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-lofi-muted">Min growth score</label>
          <input
            type="number" value={minGrowth} step={5} min={0} max={100}
            onChange={e => setMinGrowth(Number(e.target.value))}
            className="bg-lofi-surface border border-lofi-border rounded px-3 py-2 text-sm w-36 focus:outline-none focus:border-white/40"
          />
        </div>
        <div className="flex items-end">
          <button
            type="submit"
            className="px-4 py-2 rounded bg-lofi-accent text-black text-sm font-semibold hover:brightness-110 transition"
          >
            Refresh
          </button>
        </div>
      </form>

      {loading && <p className="text-lofi-muted text-sm">Loading…</p>}

      {results && (
        <>
          <div className="flex items-baseline gap-3 mb-4">
            <p className="text-xs text-lofi-muted">
              {results.total} artists  ·  below {(results.listener_threshold / 1000).toFixed(0)}k listeners
            </p>
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-lofi-muted text-xs border-b border-lofi-border">
                <th className="pb-2 font-normal w-6">#</th>
                <th className="pb-2 font-normal">Artist</th>
                <th className="pb-2 font-normal text-right">LOFI Fit</th>
                <th className="pb-2 font-normal text-right">Listeners</th>
                <th className="pb-2 font-normal text-right">Growth</th>
                <th className="pb-2 font-normal text-right">Momentum</th>
              </tr>
            </thead>
            <tbody>
              {results.artists.map((a, i) => (
                <tr
                  key={a.id}
                  className="border-b border-lofi-border/50 hover:bg-lofi-surface/50 transition-colors"
                >
                  <td className="py-2.5 text-lofi-muted text-xs">{i + 1}</td>
                  <td className="py-2.5">
                    <Link to={`/artists/${a.id}`} className="hover:text-lofi-accent transition-colors">
                      {a.name}
                    </Link>
                  </td>
                  <td className="py-2.5 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-1.5 bg-lofi-border rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-lofi-accent/60"
                          style={{ width: `${a.lofi_similarity}%` }}
                        />
                      </div>
                      <SimilarityBadge score={a.lofi_similarity} />
                    </div>
                  </td>
                  <td className="py-2.5 text-right">
                    <ListenersBadge value={a.cm_sp_listeners} />
                  </td>
                  <td className="py-2.5 text-right font-mono text-xs">{a.growth_score.toFixed(1)}</td>
                  <td className="py-2.5 text-right font-mono text-xs">{a.momentum_score.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
