import { useState, useEffect, useMemo } from 'react'
import { api } from '../api'
import { showToast } from '../components/Toast'
import type { AgentProfile, ContributionDay } from '../types'

/* ── Responsive viewport hook ── */

function useViewportWidth(): number {
  const [width, setWidth] = useState(window.innerWidth)
  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return width
}

/** Return how many days of contributions to show based on viewport width. */
function getVisibleDays(viewportWidth: number): number {
  if (viewportWidth < 600) return 90    // ~3 months
  if (viewportWidth < 900) return 180   // ~6 months
  return 365                            // 12 months
}

/* ── Heatmap helpers ── */

function getHeatLevel(count: number): number {
  if (count === 0) return 0
  if (count <= 2) return 1
  if (count <= 5) return 2
  if (count <= 9) return 3
  return 4
}

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DAY_LABELS = ['Mon', '', 'Wed', '', 'Fri', '', '']

function ActivityHeatmap({ contributions }: { contributions: ContributionDay[] }) {
  const { weeks, months } = useMemo(() => {
    if (!contributions.length) return { weeks: [], months: [] }

    // Group into weeks (columns), each with 7 day slots
    const ws: { date: string; total: number; user: number; scheduled: number }[][] = []
    let currentWeek: typeof ws[0] = []

    // Pad the first week so columns align to weekdays
    const firstDate = new Date(contributions[0].date + 'T00:00:00')
    const firstDay = firstDate.getDay() // 0=Sun
    const offset = firstDay === 0 ? 6 : firstDay - 1 // Convert to Mon=0
    for (let i = 0; i < offset; i++) {
      currentWeek.push({ date: '', total: -1, user: 0, scheduled: 0 })
    }

    for (const c of contributions) {
      const total = c.user + c.scheduled
      currentWeek.push({ date: c.date, total, user: c.user, scheduled: c.scheduled })
      if (currentWeek.length === 7) {
        ws.push(currentWeek)
        currentWeek = []
      }
    }
    if (currentWeek.length > 0) {
      ws.push(currentWeek)
    }

    // Calculate month label positions
    const ms: { label: string; col: number }[] = []
    let lastMonth = -1
    for (let col = 0; col < ws.length; col++) {
      const firstValid = ws[col].find(d => d.date)
      if (firstValid) {
        const m = new Date(firstValid.date + 'T00:00:00').getMonth()
        if (m !== lastMonth) {
          ms.push({ label: MONTH_LABELS[m], col })
          lastMonth = m
        }
      }
    }

    return { weeks: ws, months: ms }
  }, [contributions])

  if (!weeks.length) return null

  const cellSize = 13
  const cellGap = 3
  const labelWidth = 32
  const headerHeight = 20
  const totalWidth = labelWidth + weeks.length * (cellSize + cellGap)
  const totalHeight = headerHeight + 7 * (cellSize + cellGap)

  return (
    <div className="heatmap-wrap">
      <svg width={totalWidth} height={totalHeight} className="heatmap-svg">
        {/* Month labels */}
        {months.map((m, i) => (
          <text
            key={i}
            x={labelWidth + m.col * (cellSize + cellGap)}
            y={12}
            className="heatmap-label"
          >
            {m.label}
          </text>
        ))}

        {/* Day labels */}
        {DAY_LABELS.map((label, i) => (
          label ? (
            <text
              key={i}
              x={0}
              y={headerHeight + i * (cellSize + cellGap) + cellSize - 2}
              className="heatmap-label"
            >
              {label}
            </text>
          ) : null
        ))}

        {/* Cells */}
        {weeks.map((week, col) =>
          week.map((day, row) => (
            day.total >= 0 ? (
              <rect
                key={`${col}-${row}`}
                x={labelWidth + col * (cellSize + cellGap)}
                y={headerHeight + row * (cellSize + cellGap)}
                width={cellSize}
                height={cellSize}
                rx={2}
                className={`heatmap-cell heatmap-cell--${getHeatLevel(day.total)}`}
              >
                <title>{day.date}: {day.total} interactions ({day.user} user, {day.scheduled} scheduled)</title>
              </rect>
            ) : null
          ))
        )}
      </svg>

      <div className="heatmap-legend">
        <span className="heatmap-legend__label">Less</span>
        {[0, 1, 2, 3, 4].map(lvl => (
          <span key={lvl} className={`heatmap-legend__cell heatmap-cell--${lvl}`} />
        ))}
        <span className="heatmap-legend__label">More</span>
      </div>
    </div>
  )
}

/* ── Stat card ── */

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="prof-stat">
      <span className="prof-stat__value">{value}</span>
      <span className="prof-stat__label">{label}</span>
      {sub && <span className="prof-stat__sub">{sub}</span>}
    </div>
  )
}

/* ── Skill bar ── */

function SkillBar({ name, count, max }: { name: string; count: number; max: number }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  return (
    <div className="prof-skill">
      <div className="prof-skill__header">
        <span className="prof-skill__name">{name}</span>
        <span className="prof-skill__count">{count}</span>
      </div>
      <div className="prof-skill__track">
        <div className="prof-skill__fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

/* ── Main page ── */

export default function Profile() {
  const [profile, setProfile] = useState<AgentProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ name: '', emoji: '', location: '', emotional_state: '' })
  const viewportWidth = useViewportWidth()

  const load = async () => {
    setLoading(true)
    try {
      const p = await api<AgentProfile>('profile')
      setProfile(p)
      setForm({
        name: p.name || '',
        emoji: p.emoji || '',
        location: p.location || '',
        emotional_state: p.emotional_state || '',
      })
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const save = async () => {
    try {
      await api('profile', { method: 'POST', body: JSON.stringify(form) })
      showToast('Profile updated', 'success')
      setEditing(false)
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  if (loading) return <div className="page"><div className="spinner" /></div>
  if (!profile) return <div className="page"><p className="text-muted">Failed to load profile</p></div>

  const usageEntries = Object.entries(profile.skill_usage || {}).sort((a, b) => b[1] - a[1])
  const maxUsage = usageEntries.length > 0 ? usageEntries[0][1] : 0
  const stats = profile.activity_stats
  const allContributions = profile.contributions || []
  const visibleDays = getVisibleDays(viewportWidth)
  const contributions = allContributions.length > visibleDays
    ? allContributions.slice(allContributions.length - visibleDays)
    : allContributions
  const totalContributions = contributions.reduce((s, d) => s + d.user + d.scheduled, 0)
  const rangeLabel = visibleDays <= 90 ? '3 months' : visibleDays <= 180 ? '6 months' : '12 months'
  const prefEntries = Object.entries(profile.preferences || {})

  return (
    <div className="page prof-page">

      {/* ── Hero header ── */}
      <div className="prof-hero">
        <div className="prof-hero__left">
          {profile.emoji && <div className="prof-hero__avatar">{profile.emoji}</div>}
          <div className="prof-hero__text">
            <h1 className="prof-hero__name">{profile.name || 'Unnamed Agent'}</h1>
            {profile.location && <p className="prof-hero__location">{profile.location}</p>}
          </div>
        </div>
        <div className="prof-hero__right">
          {profile.emotional_state && profile.emotional_state !== 'neutral' && (
            <span className="prof-hero__mood">{profile.emotional_state}</span>
          )}
          <button className="btn btn--ghost btn--sm" onClick={() => setEditing(!editing)}>
            {editing ? 'Cancel' : 'Edit'}
          </button>
        </div>
      </div>

      {/* ── Edit form (inline) ── */}
      {editing && (
        <div className="card prof-edit">
          <h3>Edit Profile</h3>
          <div className="prof-edit__grid">
            <div className="form__group">
              <label className="form__label">Name</label>
              <input className="input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="form__group">
              <label className="form__label">Emoji</label>
              <input className="input" value={form.emoji} onChange={e => setForm(f => ({ ...f, emoji: e.target.value }))} />
            </div>
            <div className="form__group">
              <label className="form__label">Location</label>
              <input className="input" value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} />
            </div>
            <div className="form__group">
              <label className="form__label">Emotional state</label>
              <input className="input" value={form.emotional_state} onChange={e => setForm(f => ({ ...f, emotional_state: e.target.value }))} />
            </div>
          </div>
          <button className="btn btn--primary" onClick={save}>Save Changes</button>
        </div>
      )}

      {/* ── Activity stats ── */}
      {stats && (
        <div className="prof-stats-row">
          <StatCard label="Today" value={stats.today} />
          <StatCard label="This Week" value={stats.this_week} />
          <StatCard label="This Month" value={stats.this_month} />
          <StatCard label="Streak" value={`${stats.streak}d`} sub="consecutive days" />
          <StatCard label="All Time" value={stats.total} />
        </div>
      )}

      {/* ── Activity heatmap ── */}
      {contributions.length > 0 && (
        <div className="card prof-activity">
          <div className="prof-activity__header">
            <h3>Activity</h3>
            <span className="text-muted">{totalContributions} interactions in the last {rangeLabel}</span>
          </div>
          <ActivityHeatmap contributions={contributions} />
        </div>
      )}

      {/* ── Two-column bottom section ── */}
      <div className="prof-grid">
        {/* Skill usage */}
        {usageEntries.length > 0 && (
          <div className="card">
            <h3>Skill Usage</h3>
            <div className="prof-skills">
              {usageEntries.map(([skill, count]) => (
                <SkillBar key={skill} name={skill} count={count} max={maxUsage} />
              ))}
            </div>
          </div>
        )}

        {/* Status & preferences */}
        <div className="card">
          <h3>Status</h3>
          <div className="prof-meta">
            <div className="prof-meta__row">
              <span className="prof-meta__label">Emotional state</span>
              <span className="prof-meta__badge">{profile.emotional_state || 'neutral'}</span>
            </div>
            {prefEntries.length > 0 && prefEntries.map(([key, val]) => (
              <div className="prof-meta__row" key={key}>
                <span className="prof-meta__label">{key}</span>
                <span className="prof-meta__value">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
