import { useState, useEffect, useMemo } from 'react'
import { api } from '../api'
import { showToast } from '../components/Toast'
import { IconMessage, IconClock, IconSearch, IconTrash, IconRefresh, IconX, IconUser, IconZap } from '../components/Icons'
import type { Session, SessionStats } from '../types'

/* ── helpers ─────────────────────────────────────────────────── */

function relativeTime(ts: number | string): string {
  try {
    const d = typeof ts === 'number'
      ? new Date(ts < 1e12 ? ts * 1000 : ts)
      : new Date(ts)
    if (isNaN(d.getTime())) return ''
    const now = Date.now()
    const diffS = Math.floor((now - d.getTime()) / 1000)
    if (diffS < 60) return 'just now'
    const diffM = Math.floor(diffS / 60)
    if (diffM < 60) return `${diffM}m ago`
    const diffH = Math.floor(diffM / 60)
    if (diffH < 24) return `${diffH}h ago`
    const diffD = Math.floor(diffH / 24)
    if (diffD < 7) return `${diffD}d ago`
    if (diffD < 30) return `${Math.floor(diffD / 7)}w ago`
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch { return '' }
}

function modelColor(model: string): string {
  const m = model.toLowerCase()
  if (m.includes('claude')) return 'var(--gold)'
  if (m.includes('gpt-4')) return 'var(--blue)'
  if (m.includes('gpt-5')) return 'var(--ok)'
  if (m.includes('codex')) return '#a78bfa'
  return 'var(--text-2)'
}

/* ── component ───────────────────────────────────────────────── */

export default function Sessions() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [stats, setStats] = useState<SessionStats | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<{ messages: { role: string; content: string; timestamp: number }[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    if (!search.trim()) return sessions
    const q = search.toLowerCase()
    return sessions.filter(s =>
      (s.title?.toLowerCase().includes(q)) ||
      s.model.toLowerCase().includes(q) ||
      s.id.toLowerCase().includes(q)
    )
  }, [sessions, search])

  const load = async () => {
    setLoading(true)
    try {
      const [s, st] = await Promise.all([
        api<Session[]>('sessions'),
        api<SessionStats>('sessions/stats'),
      ])
      setSessions(s)
      setStats(st)
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const loadDetail = async (id: string) => {
    if (id === selectedId) return
    setSelectedId(id)
    setDetailLoading(true)
    try {
      const d = await api<{ messages: { role: string; content: string; timestamp: number }[] }>(`sessions/${id}`)
      setDetail(d)
    } catch (e: any) {
      showToast(e.message, 'error')
    }
    setDetailLoading(false)
  }

  const deleteSession = async (id: string) => {
    if (!confirm('Delete this session?')) return
    try {
      await api(`sessions/${id}`, { method: 'DELETE' })
      showToast('Session deleted', 'success')
      setSelectedId(null)
      setDetail(null)
      load()
    } catch (e: any) {
      showToast(e.message, 'error')
    }
  }

  const closeDetail = () => { setSelectedId(null); setDetail(null) }

  const selectedSession = sessions.find(s => s.id === selectedId)

  return (
    <div className="page page--sessions">
      {/* ── header ── */}
      <div className="page__header">
        <h1>Sessions</h1>
        <button className="btn btn--ghost btn--sm" onClick={load} title="Refresh">
          <IconRefresh width={14} height={14} />
          <span>Refresh</span>
        </button>
      </div>

      {/* ── stats ── */}
      {stats && (
        <div className="sess-stats">
          <div className="sess-stat">
            <div className="sess-stat__icon sess-stat__icon--sessions"><IconMessage width={16} height={16} /></div>
            <div className="sess-stat__body">
              <span className="sess-stat__value">{stats.total_sessions}</span>
              <span className="sess-stat__label">Sessions</span>
            </div>
          </div>
          <div className="sess-stat">
            <div className="sess-stat__icon sess-stat__icon--messages"><IconZap width={16} height={16} /></div>
            <div className="sess-stat__body">
              <span className="sess-stat__value">{stats.total_messages}</span>
              <span className="sess-stat__label">Messages</span>
            </div>
          </div>
          <div className="sess-stat">
            <div className="sess-stat__icon sess-stat__icon--avg"><IconClock width={16} height={16} /></div>
            <div className="sess-stat__body">
              <span className="sess-stat__value">
                {stats.total_sessions ? (stats.total_messages / stats.total_sessions).toFixed(1) : '0'}
              </span>
              <span className="sess-stat__label">Avg / Session</span>
            </div>
          </div>
        </div>
      )}

      {/* ── main layout ── */}
      <div className="sess-layout">
        {/* ── sidebar list ── */}
        <div className="sess-sidebar">
          <div className="sess-search">
            <IconSearch width={14} height={14} className="sess-search__icon" />
            <input
              type="text"
              className="sess-search__input"
              placeholder="Search sessions..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <button className="sess-search__clear" onClick={() => setSearch('')}>
                <IconX width={12} height={12} />
              </button>
            )}
          </div>

          <div className="sess-list">
            {loading && <div className="sess-list__loading"><div className="spinner" /></div>}

            {!loading && filtered.length === 0 && (
              <div className="sess-list__empty">
                <IconMessage width={28} height={28} style={{ opacity: 0.2 }} />
                <p>{search ? 'No matching sessions' : 'No sessions yet'}</p>
              </div>
            )}

            {filtered.map(s => {
              const active = selectedId === s.id
              return (
                <button
                  key={s.id}
                  className={`sess-card ${active ? 'sess-card--active' : ''}`}
                  onClick={() => loadDetail(s.id)}
                >
                  <div className="sess-card__row">
                    <span className="sess-card__model" style={{ color: modelColor(s.model) }}>
                      {s.model}
                    </span>
                    <span className="sess-card__time">{relativeTime(s.created_at)}</span>
                  </div>
                  <div className="sess-card__preview">
                    {s.title || 'Empty session'}
                  </div>
                  <div className="sess-card__footer">
                    <span className="sess-card__count">{s.message_count} msg{s.message_count !== 1 ? 's' : ''}</span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* ── detail panel ── */}
        <div className="sess-detail">
          {!selectedId && (
            <div className="sess-detail__empty">
              <IconMessage width={40} height={40} style={{ opacity: 0.12 }} />
              <p>Select a session to view its conversation</p>
            </div>
          )}

          {selectedId && detailLoading && (
            <div className="sess-detail__empty"><div className="spinner" /></div>
          )}

          {selectedId && !detailLoading && detail && (
            <>
              <div className="sess-detail__header">
                <div className="sess-detail__title">
                  <h3>Session {selectedId.slice(0, 8)}</h3>
                  {selectedSession && (
                    <span className="sess-detail__model" style={{ color: modelColor(selectedSession.model) }}>
                      {selectedSession.model}
                    </span>
                  )}
                </div>
                <div className="sess-detail__actions">
                  <button className="btn btn--danger btn--sm" onClick={() => deleteSession(selectedId)} title="Delete session">
                    <IconTrash width={13} height={13} />
                    <span>Delete</span>
                  </button>
                  <button className="btn btn--ghost btn--sm" onClick={closeDetail} title="Close">
                    <IconX width={14} height={14} />
                  </button>
                </div>
              </div>

              <div className="sess-messages">
                {detail.messages.length === 0 && (
                  <div className="sess-detail__empty" style={{ padding: '40px 0' }}>
                    <p>No messages in this session</p>
                  </div>
                )}
                {detail.messages.map((m, i) => (
                  <div key={i} className={`sess-bubble sess-bubble--${m.role}`}>
                    <div className="sess-bubble__avatar">
                      {m.role === 'user'
                        ? <IconUser width={14} height={14} />
                        : <IconZap width={14} height={14} />}
                    </div>
                    <div className="sess-bubble__body">
                      <div className="sess-bubble__head">
                        <span className="sess-bubble__role">{m.role === 'user' ? 'You' : 'Assistant'}</span>
                        <span className="sess-bubble__time">{relativeTime(m.timestamp)}</span>
                      </div>
                      <p className="sess-bubble__text">{m.content}</p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
