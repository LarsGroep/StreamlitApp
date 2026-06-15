import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { searchArtists } from '../api/client'

export default function Search() {
  const [query,      setQuery]      = useState('')
  const [minGrowth,  setMinGrowth]  = useState('')
  const [minMomentum,setMinMomentum]= useState('')
  const [lofiBooked, setLofiBooked] = useState('')
  const [results,    setResults]    = useState(null)
  const [loading,    setLoading]    = useState(false)

  async function handleSearch(e) {
    e?.preventDefault()
    setLoading(true)
    const params = {}
    if (query)       params.q            = query
    if (minGrowth)   params.min_growth   = Number(minGrowth)
    if (minMomentum) params.min_momentum = Number(minMomentum)
    if (lofiBooked !== '') params.lofi_booked = Number(lofiBooked)
    try {
      const r = await searchArtists(params)
      setResults(r.data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Search Artists</h1>

      <form onSubmit={handleSearch} className="flex flex-wrap gap-3 mb-8">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Artist name…"
          className="bg-lofi-surface border border-lofi-border rounded px-3 py-2 text-sm focus:outline-none focus:border-white/40 w-52"
        />
        <input
          value={minGrowth}
          onChange={e => setMinGrowth(e.target.value)}
          placeholder="Min growth score"
          type="number" min="0" max="100" step="1"
          className="bg-lofi-surface border border-lofi-border rounded px-3 py-2 text-sm focus:outline-none focus:border-white/40 w-40"
        />
        <input
          value={minMomentum}
          onChange={e => setMinMomentum(e.target.value)}
          placeholder="Min momentum"
          type="number" min="0" max="100" step="1"
          className="bg-lofi-surface border border-lofi-border rounded px-3 py-2 text-sm focus:outline-none focus:border-white/40 w-36"
        />
        <select
          value={lofiBooked}
          onChange={e => setLofiBooked(e.target.value)}
          className="bg-lofi-surface border border-lofi-border rounded px-3 py-2 text-sm focus:outline-none focus:border-white/40"
        >
          <option value="">All artists</option>
          <option value="1">LOFI booked</option>
          <option value="0">Not yet booked</option>
        </select>
        <button
          type="submit"
          className="px-4 py-2 rounded bg-lofi-accent text-black text-sm font-semibold hover:brightness-110 transition"
        >
          Search
        </button>
      </form>

      {loading && <p className="text-lofi-muted text-sm">Searching…</p>}

      {results && (
        <>
          <p className="text-xs text-lofi-muted mb-4">{results.total} artists found</p>
          <div className="grid gap-2">
            {results.artists.map(a => (
              <Link
                key={a.id}
                to={`/artists/${a.id}`}
                className="flex items-center justify-between bg-lofi-surface border border-lofi-border rounded px-4 py-3 hover:border-white/30 transition-colors"
              >
                <span className="font-medium">{a.name}</span>
                <div className="flex items-center gap-6 text-xs text-lofi-muted">
                  <span>Growth <span className="text-lofi-text font-mono">{a.growth_score.toFixed(1)}</span></span>
                  <span>Momentum <span className="text-lofi-text font-mono">{a.momentum_score.toFixed(1)}</span></span>
                  {a.lfm_listeners > 0 && (
                    <span>{(a.lfm_listeners / 1000).toFixed(0)}k listeners</span>
                  )}
                  {a.lofi_booked ? <span className="text-lofi-accent">LOFI ●</span> : null}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
