import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getArtist, explainArtist } from '../api/client'
import ScoreBar from '../components/ScoreBar'
import FeedbackForm from '../components/FeedbackForm'
import ShapExplainer from '../components/ShapExplainer'

function Stat({ label, value }) {
  if (value == null || value === 0) return null
  return (
    <div className="bg-lofi-surface border border-lofi-border rounded px-3 py-2">
      <div className="text-lofi-muted text-xs">{label}</div>
      <div className="font-mono text-sm mt-0.5">
        {typeof value === 'number' && value > 999
          ? (value / 1000).toFixed(1) + 'k'
          : value}
      </div>
    </div>
  )
}

function ValidationPill({ event }) {
  return (
    <span className="inline-block text-xs px-2 py-0.5 rounded-full border border-lofi-border text-lofi-muted">
      {event.event_type.replace(/_/g, ' ')}
    </span>
  )
}

export default function ArtistProfile() {
  const { id }          = useParams()
  const [artist, setArtist]   = useState(null)
  const [explain, setExplain] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab]         = useState('overview')  // overview | explain | feedback
  const [modelType, setModelType] = useState('ebm')   // ebm | xgb

  function load() {
    setLoading(true)
    getArtist(id)
      .then(r => setArtist(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  useEffect(() => {
    if (tab === 'explain') {
      setExplain(null)
      explainArtist(id, 'breakout', modelType).then(r => setExplain(r.data)).catch(() => {})
    }
  }, [tab, id, modelType])

  if (loading) return <p className="text-lofi-muted text-sm">Loading…</p>
  if (!artist)  return <p className="text-red-400 text-sm">Artist not found.</p>

  const scores = artist.scores

  return (
    <div className="max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{artist.name}</h1>
          <div className="flex items-center gap-3 mt-1">
            {artist.lofi_booked ? (
              <span className="text-xs text-lofi-accent border border-lofi-accent/40 rounded-full px-2 py-0.5">
                LOFI booked × {artist.lofi_appearances}
              </span>
            ) : (
              <span className="text-xs text-lofi-muted border border-lofi-border rounded-full px-2 py-0.5">
                Not booked
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-5 gap-2">
        <Stat label="Spotify listeners" value={artist.cm_sp_listeners} />
        <Stat label="LFM listeners"     value={artist.lfm_listeners} />
        <Stat label="LFM 90d growth"    value={artist.lfm_growth_90d != null ? `${(artist.lfm_growth_90d * 100).toFixed(1)}%` : null} />
        <Stat label="PF fans"           value={artist.pf_fans} />
        <Stat label="Past perfs"        value={artist.pf_past_perfs} />
      </div>

      {/* LOFI similarity score */}
      {artist.lofi_similarity != null && (
        <div className="flex items-center gap-4 bg-lofi-surface border border-lofi-border rounded px-4 py-3">
          <div className="flex-1">
            <div className="text-xs text-lofi-muted mb-1.5">LOFI Feel Match</div>
            <div className="h-2 bg-lofi-border rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-lofi-accent/70 transition-all"
                style={{ width: `${artist.lofi_similarity}%` }}
              />
            </div>
          </div>
          <span className="text-2xl font-bold font-mono text-lofi-accent">
            {artist.lofi_similarity.toFixed(0)}
          </span>
          <span className="text-xs text-lofi-muted">/100</span>
        </div>
      )}

      {/* Scores */}
      {scores && (
        <div className="bg-lofi-surface border border-lofi-border rounded p-4 space-y-3">
          <h2 className="text-xs text-lofi-muted uppercase tracking-widest mb-3">Scores</h2>
          <ScoreBar label="Growth"           value={scores.growth_score}      accent />
          <ScoreBar label="Momentum"         value={scores.momentum_score} />
          <ScoreBar label="Market Relevance" value={scores.market_relevance} />
          <ScoreBar label="Future Potential" value={scores.future_potential} />
          <ScoreBar label="Confidence"       value={scores.confidence_score} max={100} />
          <p className="text-xs text-lofi-muted text-right pt-1">
            Updated {new Date(scores.computed_at).toLocaleDateString()}
          </p>
        </div>
      )}

      {/* Validation events */}
      {artist.validation_events.length > 0 && (
        <div>
          <h2 className="text-xs text-lofi-muted uppercase tracking-widest mb-2">Milestones</h2>
          <div className="flex flex-wrap gap-2">
            {artist.validation_events.map((ve, i) => (
              <ValidationPill key={i} event={ve} />
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-lofi-border flex gap-4">
        {['overview', 'explain', 'feedback'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`text-sm pb-2 capitalize transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'border-lofi-accent text-lofi-accent'
                : 'border-transparent text-lofi-muted hover:text-lofi-text'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && (
        <div>
          {artist.feedback.length > 0 ? (
            <div className="space-y-2">
              <h2 className="text-xs text-lofi-muted uppercase tracking-widest mb-2">Booking Team Notes</h2>
              {artist.feedback.map(fb => (
                <div key={fb.id} className="bg-lofi-surface border border-lofi-border rounded px-4 py-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-lofi-accent capitalize">{fb.category.replace(/_/g, ' ')}</span>
                    <span className="text-xs text-lofi-muted">{new Date(fb.created_at).toLocaleDateString()}</span>
                  </div>
                  {fb.notes && <p className="text-sm mt-1 text-lofi-muted">{fb.notes}</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-lofi-muted text-sm">No team feedback yet.</p>
          )}
        </div>
      )}

      {tab === 'explain' && (
        <div className="space-y-4">
          {/* Model type toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-lofi-muted">Model:</span>
            {['ebm', 'xgb'].map(t => (
              <button
                key={t}
                onClick={() => setModelType(t)}
                className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                  modelType === t
                    ? 'border-lofi-accent text-lofi-accent'
                    : 'border-lofi-border text-lofi-muted hover:border-white/30'
                }`}
              >
                {t === 'ebm' ? 'EBM (glass-box)' : 'XGBoost + SHAP'}
              </button>
            ))}
          </div>

          {!explain && <p className="text-lofi-muted text-sm">Loading explanation…</p>}
          {explain && (
            <div className="space-y-4">
              <div className="flex items-baseline gap-3">
                <span className="text-xs text-lofi-muted">Breakout probability</span>
                <span className="text-2xl font-bold text-lofi-accent">
                  {(explain.prediction * 100).toFixed(0)}%
                </span>
                <span className="text-xs text-lofi-muted">{explain.model_type?.toUpperCase()}</span>
              </div>
              <h2 className="text-xs text-lofi-muted uppercase tracking-widest">Feature Contributions</h2>
              <ShapExplainer features={explain.top_features} />
            </div>
          )}
        </div>
      )}

      {tab === 'feedback' && (
        <FeedbackForm artistId={id} onSubmitted={load} />
      )}
    </div>
  )
}
