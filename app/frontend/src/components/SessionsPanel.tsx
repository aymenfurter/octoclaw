import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { IconPlus, IconClock } from './Icons'
import type { Session } from '../types'

interface Props {
  open: boolean
  onClose: () => void
}

export default function SessionsPanel({ open, onClose }: Props) {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<Session[]>([])

  useEffect(() => {
    if (open) {
      api<Session[]>('sessions').then(setSessions).catch(() => {})
    }
  }, [open])

  const goSession = (id: string) => {
    navigate(`/chat?session=${id}`)
    onClose()
  }

  return (
    <aside className={`panel ${open ? '' : 'panel--hidden'}`}>
      <div className="panel__header">
        <span className="panel__title">Recent Sessions</span>
        <button
          className="btn btn--ghost btn--sm"
          onClick={() => { navigate('/chat'); onClose() }}
          title="New chat"
        >
          <IconPlus width={14} height={14} />
        </button>
      </div>
      <div className="panel__list">
        {sessions.length === 0 && (
          <p style={{ padding: '16px', fontSize: 12, color: 'var(--text-3)' }}>No sessions yet</p>
        )}
        {sessions.map(s => (
          <button
            key={s.id}
            className="panel__item"
            onClick={() => goSession(s.id)}
          >
            <span className="panel__item-preview">
              {s.title || 'Empty session'}
            </span>
            <span className="panel__item-meta">
              <span>{s.model}</span>
              <span>{formatTime(s.created_at)}</span>
              <span>{s.message_count} msgs</span>
            </span>
          </button>
        ))}
      </div>
      <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
        <button
          className="btn btn--ghost btn--sm"
          onClick={() => { navigate('/sessions'); onClose() }}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          <IconClock width={14} height={14} />
          <span>All Sessions</span>
        </button>
      </div>
    </aside>
  )
}

function formatTime(ts: number | string): string {
  try {
    const d = typeof ts === 'number'
      ? new Date(ts < 1e12 ? ts * 1000 : ts)
      : new Date(ts)
    if (isNaN(d.getTime())) return String(ts)
    const now = Date.now()
    const diffS = Math.floor((now - d.getTime()) / 1000)
    if (diffS < 60) return 'just now'
    const diffM = Math.floor(diffS / 60)
    if (diffM < 60) return `${diffM}m ago`
    const diffH = Math.floor(diffM / 60)
    if (diffH < 24) return `${diffH}h ago`
    const diffD = Math.floor(diffH / 24)
    if (diffD < 7) return `${diffD}d ago`
    return d.toLocaleDateString()
  } catch { return String(ts) }
}
