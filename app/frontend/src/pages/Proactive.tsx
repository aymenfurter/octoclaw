import { useState, useEffect } from 'react'
import { api } from '../api'
import { showToast } from '../components/Toast'
import type { ProactiveState } from '../types'

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return 'Never'
  const then = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - then.getTime()
  if (diffMs < 0) return 'just now'
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ${mins % 60}m ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

export function ProactiveContent() {
  const [state, setState] = useState<ProactiveState | null>(null)
  const [loading, setLoading] = useState(true)
  const [prefs, setPrefs] = useState({ minGap: 4, maxDaily: 3, preferredTimes: '', avoidedTopics: '' })
  const [forming, setForming] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const s = await api<ProactiveState>('proactive')
      setState(s)
      if (s.preferences) {
        setPrefs({
          minGap: s.preferences.min_gap_hours ?? 4,
          maxDaily: s.preferences.max_daily ?? 3,
          preferredTimes: s.preferences.preferred_times || '',
          avoidedTopics: (s.preferences.avoided_topics || []).join(', '),
        })
      }
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const forceMemory = async () => {
    setForming(true)
    try {
      const res = await api<{ status: string; message?: string }>('proactive/memory/form', { method: 'POST' })
      if (res.status === 'ok') showToast('Memory formation complete', 'success')
      else showToast(res.message || res.status, 'error')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
    setForming(false)
  }

  const toggleEnabled = async () => {
    try {
      await api('proactive/enabled', {
        method: 'PUT', body: JSON.stringify({ enabled: !state?.enabled }),
      })
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const cancelPending = async () => {
    try {
      await api('proactive/pending', { method: 'DELETE' })
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const savePrefs = async () => {
    try {
      await api('proactive/preferences', {
        method: 'PUT',
        body: JSON.stringify({
          min_gap_hours: prefs.minGap,
          max_daily: prefs.maxDaily,
          preferred_times: prefs.preferredTimes,
          avoided_topics: prefs.avoidedTopics.split(',').map(s => s.trim()).filter(Boolean),
        }),
      })
      showToast('Preferences saved', 'success')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  if (loading) return <div className="spinner" />
  if (!state) return <p className="text-muted">Failed to load</p>

  return (
    <>
      <div className="page__header">
        <h1>Proactive Follow-ups</h1>
        <button className="btn btn--ghost btn--sm" onClick={load}>Refresh</button>
      </div>

      <div className="stats-bar">
        <div className="stat">
          <span className="stat__value">{state.messages_sent_today ?? 0}</span>
          <span className="stat__label">Sent Today</span>
        </div>
        <div className="stat">
          <span className="stat__value">{state.hours_since_last_sent != null ? `${state.hours_since_last_sent.toFixed(1)}h` : 'Never'}</span>
          <span className="stat__label">Last Sent</span>
        </div>
        <div className="stat">
          <span className="stat__value">{state.conversation_refs ?? 0}</span>
          <span className="stat__label">Channels</span>
        </div>
      </div>

      {state.memory && (
        <div className="card">
          <h3>Memory Agent</h3>
          <div className="stats-bar">
            <div className="stat">
              <span className="stat__value">{state.memory.forming_now ? 'Running' : 'Idle'}</span>
              <span className="stat__label">Status</span>
            </div>
            <div className="stat">
              <span className="stat__value">{timeAgo(state.memory.last_formed_at)}</span>
              <span className="stat__label">Last Run</span>
            </div>
            <div className="stat">
              <span className="stat__value">{state.memory.formation_count}</span>
              <span className="stat__label">Total Runs</span>
            </div>
            <div className="stat">
              <span className="stat__value">{state.memory.buffered_turns}</span>
              <span className="stat__label">Buffered Turns</span>
            </div>
          </div>
          <div style={{marginTop: 12, display: 'flex', alignItems: 'center', gap: 12}}>
            <button
              className="btn btn--primary btn--sm"
              onClick={forceMemory}
              disabled={forming || state.memory.forming_now || state.memory.buffered_turns === 0}
            >
              {forming || state.memory.forming_now ? 'Forming...' : 'Form Memory Now'}
            </button>
            {state.memory.buffered_turns === 0 && (
              <span className="text-muted text-sm">No buffered turns to process</span>
            )}
          </div>
          {state.memory.timer_active && (
            <p className="text-muted text-sm" style={{marginTop: 8}}>
              Idle timer active -- will form memory after {state.memory.idle_minutes}m of inactivity
            </p>
          )}
          {state.memory.last_error && (
            <p className="text-danger text-sm" style={{marginTop: 8}}>
              Last error: {state.memory.last_error}
            </p>
          )}
          {state.memory.last_proactive_scheduled && (
            <p className="text-sm" style={{marginTop: 8, color: 'var(--gold)'}}>
              Last run scheduled a proactive follow-up
            </p>
          )}
        </div>
      )}

      <div className="card">
        <div className="card__row">
          <label className="form__check">
            <input type="checkbox" checked={state.enabled} onChange={toggleEnabled} />
            Enable proactive follow-ups
          </label>
        </div>
      </div>

      {state.pending && (
        <div className="card">
          <h3>Pending Follow-up</h3>
          <p><strong>Deliver at:</strong> {new Date(state.pending.deliver_at).toLocaleString()}</p>
          <p><strong>Message:</strong> {state.pending.message}</p>
          {state.pending.context && <p className="text-muted">{state.pending.context}</p>}
          <button className="btn btn--danger btn--sm" onClick={cancelPending}>Cancel</button>
        </div>
      )}

      <div className="card">
        <h3>Preferences</h3>
        <div className="form">
          <div className="form__row">
            <div className="form__group">
              <label className="form__label">Min gap (hours)</label>
              <input type="number" className="input" value={prefs.minGap} onChange={e => setPrefs(p => ({ ...p, minGap: +e.target.value }))} />
            </div>
            <div className="form__group">
              <label className="form__label">Max daily</label>
              <input type="number" className="input" value={prefs.maxDaily} onChange={e => setPrefs(p => ({ ...p, maxDaily: +e.target.value }))} />
            </div>
          </div>
          <div className="form__group">
            <label className="form__label">Preferred times</label>
            <input className="input" value={prefs.preferredTimes} onChange={e => setPrefs(p => ({ ...p, preferredTimes: e.target.value }))} placeholder="e.g. 9:00-12:00, 14:00-17:00" />
          </div>
          <div className="form__group">
            <label className="form__label">Avoided topics (comma-separated)</label>
            <input className="input" value={prefs.avoidedTopics} onChange={e => setPrefs(p => ({ ...p, avoidedTopics: e.target.value }))} />
          </div>
          <button className="btn btn--primary btn--sm" onClick={savePrefs}>Save Preferences</button>
        </div>
      </div>

      {state.history && state.history.length > 0 && (
        <div className="card">
          <h3>History</h3>
          <div className="list">
            {[...state.history].reverse().map((h, i) => (
              <div key={i} className="list-item">
                <div className="list-item__body">
                  <div className="list-item__top">
                    <span className="text-muted">{new Date(h.delivered_at).toLocaleString()}</span>
                    {h.reaction && <span className="badge">{h.reaction}</span>}
                  </div>
                  <div className="list-item__desc">{h.message}</div>
                  {h.context && <div className="text-muted text-sm">{h.context}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}

export default function Proactive() {
  return <div className="page"><ProactiveContent /></div>
}
