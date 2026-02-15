import { useState, useEffect } from 'react'
import { api, apiFormData } from '../api'
import { showToast } from '../components/Toast'
import Breadcrumb from '../components/Breadcrumb'
import type { Plugin } from '../types'

export default function Plugins() {
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api<{ plugins: Plugin[] }>('plugins')
      setPlugins(r.plugins || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const togglePlugin = async (p: Plugin) => {
    const action = p.enabled ? 'disable' : 'enable'
    try {
      await api(`plugins/${p.id}/${action}`, { method: 'POST' })
      showToast(`Plugin ${p.name} ${action}d`, 'success')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const removePlugin = async (p: Plugin) => {
    if (!confirm(`Remove plugin "${p.name}"?`)) return
    try {
      await api(`plugins/${p.id}`, { method: 'DELETE' })
      showToast('Plugin removed', 'success')
      setSelectedPlugin(null)
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const importPlugin = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    try {
      const r = await apiFormData<{ status: string; plugin: { name: string } }>('plugins/import', fd)
      showToast(`Plugin "${r.plugin.name}" imported`, 'success')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
    e.target.value = ''
  }


  return (
    <div className="page">
      <Breadcrumb current="Plugins" parentPath="/customization" parentLabel="Customization" />
      <div className="page__header">
        <h1>Plugins</h1>
        <div className="page__actions">
          <label className="btn btn--secondary btn--sm">
            Import ZIP
            <input type="file" accept=".zip" hidden onChange={importPlugin} />
          </label>
          <button className="btn btn--ghost btn--sm" onClick={load}>Refresh</button>
        </div>
      </div>

      {loading && <div className="spinner" />}

      <div className="grid grid--cards">
        {plugins.map(p => (
          <div key={p.id} className={`plugin-card card ${p.enabled ? 'plugin-card--enabled' : ''}`}>
            <div className="plugin-card__header">
              <div>
                <h3>{p.name}</h3>
                <span className="text-muted">v{p.version}</span>
              </div>
            </div>
            <p className="plugin-card__desc">{p.description}</p>
            <div className="plugin-card__meta">
              <span>{p.skill_count} skill{p.skill_count !== 1 ? 's' : ''}</span>
              <span>{p.source}</span>
              {p.author && <span>by {p.author}</span>}
            </div>
            {p.enabled && p.setup_skill && !p.setup_completed && (
              <div className="plugin-card__setup-badge">Setup required</div>
            )}
            <div className="plugin-card__actions">
              <button
                className={`btn btn--sm ${p.enabled ? 'btn--secondary' : 'btn--primary'}`}
                onClick={() => togglePlugin(p)}
              >
                {p.enabled ? 'Disable' : 'Enable'}
              </button>
              <button className="btn btn--ghost btn--sm" onClick={() => setSelectedPlugin(p)}>Details</button>
            </div>
          </div>
        ))}
        {!loading && plugins.length === 0 && <p className="text-muted">No plugins found</p>}
      </div>

      {/* Detail Modal */}
      {selectedPlugin && (
        <div className="modal-overlay" onClick={() => setSelectedPlugin(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal__header">
              <h2>{selectedPlugin.name}</h2>
              <button className="btn btn--ghost btn--sm" onClick={() => setSelectedPlugin(null)}>&times;</button>
            </div>
            <div className="modal__body">
              <p>{selectedPlugin.description}</p>
              <div className="detail-grid">
                <div><strong>Version:</strong> {selectedPlugin.version}</div>
                <div><strong>Source:</strong> {selectedPlugin.source}</div>
                <div><strong>Skills:</strong> {selectedPlugin.skill_count}</div>
                {selectedPlugin.author && <div><strong>Author:</strong> {selectedPlugin.author}</div>}
                {selectedPlugin.homepage && <div><strong>Homepage:</strong> <a href={selectedPlugin.homepage} target="_blank" rel="noopener">{selectedPlugin.homepage}</a></div>}
              </div>
              {selectedPlugin.skills && selectedPlugin.skills.length > 0 && (
                <div>
                  <h4>Included Skills</h4>
                  <ul>{selectedPlugin.skills.map(s => <li key={s}>{s}</li>)}</ul>
                </div>
              )}
            </div>
            <div className="modal__footer">
              <button className={`btn ${selectedPlugin.enabled ? 'btn--danger' : 'btn--primary'}`} onClick={() => { togglePlugin(selectedPlugin); setSelectedPlugin(null) }}>
                {selectedPlugin.enabled ? 'Disable' : 'Enable'}
              </button>
              {selectedPlugin.source === 'user' && (
                <button className="btn btn--danger" onClick={() => { removePlugin(selectedPlugin); }}>Remove</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
