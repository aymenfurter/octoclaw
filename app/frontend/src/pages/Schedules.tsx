import { useState, useEffect, useMemo } from 'react'
import { api } from '../api'
import { showToast } from '../components/Toast'
import Breadcrumb from '../components/Breadcrumb'
import type { Schedule } from '../types'

/* ── Colour palette for schedule heatmap ─────────────────────────────── */

const SCHED_COLORS = [
  '#58A6FF', // blue
  '#D29922', // gold
  '#3FB950', // green
  '#F85149', // red
  '#bc8cff', // purple
  '#f0883e', // orange
  '#39d353', // lime
  '#db61a2', // pink
]

/* ── Helpers ─────────────────────────────────────────────────────────── */

/** Format a date/time string for display */
function fmtDate(d?: string | null) {
  if (!d) return null
  try { return new Date(d).toLocaleString() } catch { return d }
}

/** Describe when a schedule fires */
function triggerLabel(s: Schedule) {
  if (s.cron) return `cron: ${s.cron}`
  if (s.run_at) {
    try { return `once: ${new Date(s.run_at).toLocaleString()}` } catch { return `once: ${s.run_at}` }
  }
  return 'no trigger'
}

/* ── Heatmap computation ─────────────────────────────────────────────── */

interface HeatCell {
  date: string          // YYYY-MM-DD
  dayLabel: string      // "Mon", "Tue", etc.
  hours: { hour: number; items: { id: string; description: string; colorIdx: number }[] }[]
}

/**
 * Parse a standard 5-field cron expression and yield upcoming fire times
 * within a date range. Lightweight client-side implementation covering the
 * most common patterns (specific values, *, ranges, steps, and lists).
 */
function* cronFireTimes(cron: string, from: Date, to: Date): Generator<Date> {
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 5) return

  function parseField(field: string, min: number, max: number): Set<number> {
    const result = new Set<number>()
    for (const token of field.split(',')) {
      // handle */n
      const stepMatch = token.match(/^(\*|(\d+)-(\d+))\/(\d+)$/)
      if (stepMatch) {
        const step = parseInt(stepMatch[4], 10)
        const start = stepMatch[2] != null ? parseInt(stepMatch[2], 10) : min
        const end = stepMatch[3] != null ? parseInt(stepMatch[3], 10) : max
        for (let i = start; i <= end; i += step) result.add(i)
        continue
      }
      if (token === '*') { for (let i = min; i <= max; i++) result.add(i); continue }
      const rangeMatch = token.match(/^(\d+)-(\d+)$/)
      if (rangeMatch) {
        const a = parseInt(rangeMatch[1], 10), b = parseInt(rangeMatch[2], 10)
        for (let i = a; i <= b; i++) result.add(i)
        continue
      }
      const n = parseInt(token, 10)
      if (!isNaN(n)) result.add(n)
    }
    return result
  }

  const minutes = parseField(parts[0], 0, 59)
  const hours = parseField(parts[1], 0, 23)
  const doms = parseField(parts[2], 1, 31)
  const months = parseField(parts[3], 1, 12)
  const dows = parseField(parts[4], 0, 6)    // 0=Sun

  const cursor = new Date(from)
  cursor.setUTCSeconds(0, 0)

  // iterate minute-by-minute would be slow; iterate hour-by-hour and check minutes
  cursor.setUTCMinutes(0)
  while (cursor <= to) {
    const m = cursor.getUTCMonth() + 1
    const dom = cursor.getUTCDate()
    const dow = cursor.getUTCDay()
    const h = cursor.getUTCHours()

    if (months.has(m) && doms.has(dom) && dows.has(dow) && hours.has(h)) {
      for (const min of minutes) {
        const fire = new Date(cursor)
        fire.setUTCMinutes(min)
        if (fire >= from && fire <= to) yield fire
      }
    }
    cursor.setTime(cursor.getTime() + 3600_000) // +1 hour
  }
}

function buildWeekPreview(schedules: Schedule[]): HeatCell[] {
  const now = new Date()
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  const cells: HeatCell[] = []
  for (let d = 0; d < 7; d++) {
    const date = new Date(today)
    date.setUTCDate(date.getUTCDate() + d)
    const key = date.toISOString().slice(0, 10)
    const dayLabel = d === 0 ? 'Today' : d === 1 ? 'Tomorrow' : dayNames[date.getUTCDay()]
    const hours: HeatCell['hours'] = []
    for (let h = 0; h < 24; h++) hours.push({ hour: h, items: [] })
    cells.push({ date: key, dayLabel, hours })
  }

  const weekEnd = new Date(today)
  weekEnd.setUTCDate(weekEnd.getUTCDate() + 7)

  schedules.forEach((s, idx) => {
    if (!s.enabled) return
    const ci = idx % SCHED_COLORS.length

    // One-time run_at
    if (s.run_at) {
      try {
        const rt = new Date(s.run_at)
        const key = rt.toISOString().slice(0, 10)
        const cell = cells.find(c => c.date === key)
        if (cell) {
          const h = rt.getUTCHours()
          cell.hours[h].items.push({ id: s.id, description: s.description, colorIdx: ci })
        }
      } catch { /* skip */ }
    }

    // Cron recurring
    if (s.cron) {
      for (const fire of cronFireTimes(s.cron, today, weekEnd)) {
        const key = fire.toISOString().slice(0, 10)
        const cell = cells.find(c => c.date === key)
        if (cell) {
          const h = fire.getUTCHours()
          // Avoid duplicate entries for same schedule in same hour
          if (!cell.hours[h].items.some(it => it.id === s.id)) {
            cell.hours[h].items.push({ id: s.id, description: s.description, colorIdx: ci })
          }
        }
      }
    }
  })

  return cells
}

/* ── Component ──────────────────────────────────────────────────────── */

export default function Schedules() {
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ description: '', cron: '', run_at: '', prompt: '', enabled: true })

  const load = async () => {
    setLoading(true)
    try {
      const r = await api<Schedule[] | { schedules?: Schedule[] }>('schedules')
      setSchedules(Array.isArray(r) ? r : (r.schedules || []))
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const openAdd = () => {
    setEditId(null)
    setForm({ description: '', cron: '0 9 * * *', run_at: '', prompt: '', enabled: true })
    setShowModal(true)
  }

  const openEdit = (s: Schedule) => {
    setEditId(s.id)
    setForm({ description: s.description, cron: s.cron || '', run_at: s.run_at || '', prompt: s.prompt, enabled: s.enabled })
    setShowModal(true)
  }

  const save = async () => {
    const body: Record<string, unknown> = {
      description: form.description,
      prompt: form.prompt,
      enabled: form.enabled,
    }
    if (form.cron) body.cron = form.cron
    if (form.run_at) body.run_at = form.run_at
    try {
      if (editId) {
        await api(`schedules/${editId}`, { method: 'PUT', body: JSON.stringify(body) })
      } else {
        await api('schedules', { method: 'POST', body: JSON.stringify(body) })
      }
      showToast(editId ? 'Schedule updated' : 'Schedule created', 'success')
      setShowModal(false)
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const remove = async (id: string) => {
    if (!confirm('Delete this schedule?')) return
    try {
      await api(`schedules/${id}`, { method: 'DELETE' })
      showToast('Deleted', 'success')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const toggle = async (s: Schedule) => {
    try {
      await api(`schedules/${s.id}`, { method: 'PUT', body: JSON.stringify({ enabled: !s.enabled }) })
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const weekPreview = useMemo(() => buildWeekPreview(schedules), [schedules])

  // Check if there are any upcoming firings
  const hasUpcoming = weekPreview.some(d => d.hours.some(h => h.items.length > 0))

  const CELL = 13
  const GAP = 2
  const COL_W = CELL + GAP
  const LABEL_W = 70    // space for day labels on the left
  const HOUR_LABEL_H = 16
  const previewW = LABEL_W + 24 * COL_W + 4
  const ROW_H = CELL + GAP
  const previewH = HOUR_LABEL_H + 7 * ROW_H + 4

  return (
    <div className="page">
      <Breadcrumb current="Schedules" parentPath="/customization" parentLabel="Customization" />
      <div className="page__header">
        <h1>Schedules</h1>
        <div className="page__actions">
          <button className="btn btn--primary btn--sm" onClick={openAdd}>New Schedule</button>
          <button className="btn btn--ghost btn--sm" onClick={load}>Refresh</button>
        </div>
      </div>

      {loading && <div className="spinner" />}

      {/* ── Week Preview ────────────────────────────────────────────── */}
      {!loading && schedules.length > 0 && (
        <div className="card" style={{ marginBottom: 20, padding: '16px 20px' }}>
          <h3 style={{ fontSize: 13, marginBottom: 4 }}>Upcoming Schedule (next 7 days)</h3>
          {!hasUpcoming && (
            <p className="text-muted" style={{ fontSize: 12, margin: '8px 0 0' }}>
              No upcoming firings in the next 7 days.
            </p>
          )}
          {hasUpcoming && (
            <>
              <div className="heatmap-wrap">
                <svg className="heatmap-svg" width={previewW} height={previewH}>
                  {/* Hour labels across the top */}
                  {Array.from({ length: 24 }, (_, h) => (
                    h % 3 === 0 ? (
                      <text
                        key={h}
                        x={LABEL_W + h * COL_W + CELL / 2}
                        y={12}
                        className="heatmap-label"
                        textAnchor="middle"
                        style={{ fontSize: 9 }}
                      >
                        {h.toString().padStart(2, '0')}
                      </text>
                    ) : null
                  ))}
                  {/* Day rows */}
                  {weekPreview.map((day, di) => (
                    <g key={day.date}>
                      {/* Day label */}
                      <text
                        x={LABEL_W - 6}
                        y={HOUR_LABEL_H + di * ROW_H + CELL - 2}
                        className="heatmap-label"
                        textAnchor="end"
                        style={{ fontSize: 10 }}
                      >
                        {day.dayLabel}
                      </text>
                      {/* Hour cells */}
                      {day.hours.map((hr) => {
                        const x = LABEL_W + hr.hour * COL_W
                        const y = HOUR_LABEL_H + di * ROW_H
                        const n = hr.items.length
                        const fill = n === 0
                          ? 'var(--surface-alt)'
                          : SCHED_COLORS[hr.items[0].colorIdx]
                        const opacity = n === 0 ? 1 : Math.min(0.4 + n * 0.3, 1)
                        const title = n === 0
                          ? `${day.date} ${hr.hour.toString().padStart(2, '0')}:00 UTC`
                          : `${day.date} ${hr.hour.toString().padStart(2, '0')}:00 UTC\n${hr.items.map(i => i.description).join('\n')}`
                        return (
                          <rect
                            key={hr.hour}
                            x={x} y={y}
                            width={CELL} height={CELL}
                            rx={2}
                            fill={fill}
                            opacity={opacity}
                          >
                            <title>{title}</title>
                          </rect>
                        )
                      })}
                    </g>
                  ))}
                </svg>
              </div>
              {/* Colour legend */}
              <div className="sched-legend">
                {schedules.filter(s => s.enabled).map((s, i) => (
                  <div key={s.id} className="sched-legend__item">
                    <span className="sched-legend__dot" style={{ background: SCHED_COLORS[i % SCHED_COLORS.length] }} />
                    <span className="sched-legend__label">{s.description}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── List ─────────────────────────────────────────────────────── */}
      {!loading && schedules.length === 0 && <p className="text-muted">No schedules configured</p>}

      <div className="list">
        {schedules.map((s, idx) => (
          <div key={s.id} className={`list-item ${!s.enabled ? 'list-item--disabled' : ''}`}>
            <span
              className="sched-dot"
              style={{ background: SCHED_COLORS[idx % SCHED_COLORS.length] }}
            />
            <div className="list-item__body">
              <div className="list-item__top">
                <strong className="list-item__title">{s.description}</strong>
                <code className="text-muted text-sm">{triggerLabel(s)}</code>
                {!s.enabled && <span className="badge badge--muted">disabled</span>}
              </div>
              <div className="list-item__desc text-muted">{s.prompt}</div>
              <div className="list-item__meta">
                {s.last_run && <span>Last run: {fmtDate(s.last_run)}</span>}
                {s.created_at && <span>Created: {fmtDate(s.created_at)}</span>}
              </div>
            </div>
            <div className="list-item__actions">
              <button className="btn btn--ghost btn--sm" onClick={() => toggle(s)}>{s.enabled ? 'Disable' : 'Enable'}</button>
              <button className="btn btn--ghost btn--sm" onClick={() => openEdit(s)}>Edit</button>
              <button className="btn btn--danger btn--sm" onClick={() => remove(s.id)}>Delete</button>
            </div>
          </div>
        ))}
      </div>

      {/* ── Modal ────────────────────────────────────────────────────── */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal__header">
              <h2>{editId ? 'Edit Schedule' : 'New Schedule'}</h2>
              <button className="btn btn--ghost btn--sm" onClick={() => setShowModal(false)}>&times;</button>
            </div>
            <div className="modal__body">
              <div className="form">
                <div className="form__group">
                  <label className="form__label">Description</label>
                  <input className="input" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="What is this schedule for?" />
                </div>
                <div className="form__group">
                  <label className="form__label">Cron Schedule</label>
                  <input className="input" value={form.cron} onChange={e => setForm(f => ({ ...f, cron: e.target.value }))} placeholder="0 9 * * *" />
                  <span className="text-muted text-sm">Standard cron syntax (min hour day month weekday). Leave empty for one-time schedules.</span>
                </div>
                <div className="form__group">
                  <label className="form__label">Run At (one-time)</label>
                  <input className="input" type="datetime-local" value={form.run_at ? form.run_at.slice(0, 16) : ''} onChange={e => setForm(f => ({ ...f, run_at: e.target.value }))} />
                  <span className="text-muted text-sm">For one-time schedules. Ignored if a cron expression is set.</span>
                </div>
                <div className="form__group">
                  <label className="form__label">Prompt</label>
                  <textarea className="input" rows={4} value={form.prompt} onChange={e => setForm(f => ({ ...f, prompt: e.target.value }))} placeholder="What should the agent do?" />
                </div>
                <label className="form__check">
                  <input type="checkbox" checked={form.enabled} onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))} />
                  Enabled
                </label>
              </div>
            </div>
            <div className="modal__footer">
              <button className="btn btn--secondary" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn--primary" onClick={save}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
