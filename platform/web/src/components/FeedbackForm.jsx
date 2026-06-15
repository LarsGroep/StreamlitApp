import { useState } from 'react'
import { submitFeedback } from '../api/client'

const CATEGORIES = [
  { value: 'fits_lofi',           label: 'Fits LOFI' },
  { value: 'doesnt_fit',          label: "Doesn't Fit" },
  { value: 'sound_to_develop',    label: 'Sound to Develop' },
  { value: 'saturated',           label: 'Saturated' },
  { value: 'support_act',         label: 'Interesting Support Act' },
  { value: 'potential_headliner', label: 'Potential Future Headliner' },
]

export default function FeedbackForm({ artistId, onSubmitted }) {
  const [category, setCategory] = useState('')
  const [notes, setNotes]       = useState('')
  const [status, setStatus]     = useState(null)   // null | 'sending' | 'ok' | 'err'

  async function handleSubmit(e) {
    e.preventDefault()
    if (!category) return
    setStatus('sending')
    try {
      await submitFeedback({ artist_id: artistId, category, notes: notes || undefined })
      setStatus('ok')
      setCategory('')
      setNotes('')
      onSubmitted?.()
    } catch {
      setStatus('err')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        {CATEGORIES.map(c => (
          <button
            key={c.value}
            type="button"
            onClick={() => setCategory(c.value)}
            className={`text-xs px-3 py-2 rounded border transition-colors text-left ${
              category === c.value
                ? 'border-lofi-accent text-lofi-accent bg-lofi-accent/10'
                : 'border-lofi-border text-lofi-muted hover:border-white/30'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      <textarea
        value={notes}
        onChange={e => setNotes(e.target.value)}
        placeholder="Notes (optional)…"
        rows={2}
        className="w-full bg-lofi-surface border border-lofi-border rounded px-3 py-2 text-sm text-lofi-text placeholder-lofi-muted resize-none focus:outline-none focus:border-white/40"
      />

      <button
        type="submit"
        disabled={!category || status === 'sending'}
        className="w-full py-2 rounded bg-lofi-accent text-black text-sm font-semibold disabled:opacity-40 hover:brightness-110 transition"
      >
        {status === 'sending' ? 'Saving…' : status === 'ok' ? 'Saved ✓' : 'Save Feedback'}
      </button>
      {status === 'err' && <p className="text-red-400 text-xs">Failed — try again</p>}
    </form>
  )
}
