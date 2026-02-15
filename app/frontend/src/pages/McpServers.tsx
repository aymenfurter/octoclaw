import { useState, useEffect } from 'react'
import { api } from '../api'
import { showToast } from '../components/Toast'
import Breadcrumb from '../components/Breadcrumb'
import type { McpServer, McpRegistryEntry } from '../types'

export default function McpServers() {
  const [servers, setServers] = useState<McpServer[]>([])
  const [registry, setRegistry] = useState<McpRegistryEntry[]>([])
  const [tab, setTab] = useState<'servers' | 'discover'>('servers')
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editServer, setEditServer] = useState<McpServer | null>(null)
  const [regPage, setRegPage] = useState(1)
  const [regQuery, setRegQuery] = useState('')

  // Form state
  const [form, setForm] = useState({
    name: '', type: 'local' as 'local' | 'http' | 'sse',
    description: '', enabled: true,
    command: '', args: '', env: '', url: '',
  })

  const load = async () => {
    setLoading(true)
    try {
      const r = await api<{ servers: McpServer[] }>('mcp/servers')
      setServers(r.servers || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  const loadRegistry = async (page = 1, query = '') => {
    try {
      let url = `mcp/registry?page=${page}`
      if (query) url += `&q=${encodeURIComponent(query)}`
      const r = await api<{ servers: McpRegistryEntry[] }>(url)
      setRegistry(r.servers || [])
    } catch { /* ignore */ }
  }

  useEffect(() => { load() }, [])
  useEffect(() => { if (tab === 'discover') loadRegistry(regPage, regQuery) }, [tab, regPage])

  const toggleServer = async (name: string, enabled: boolean) => {
    try {
      await api(`mcp/servers/${encodeURIComponent(name)}/${enabled ? 'enable' : 'disable'}`, { method: 'POST' })
      showToast(`Server ${enabled ? 'enabled' : 'disabled'}`, 'success')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const removeServer = async (name: string) => {
    if (!confirm(`Remove MCP server "${name}"?`)) return
    try {
      await api(`mcp/servers/${encodeURIComponent(name)}`, { method: 'DELETE' })
      showToast('Server removed', 'success')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const openAdd = (prefill?: Partial<typeof form>) => {
    setEditServer(null)
    setForm({ name: '', type: 'local', description: '', enabled: true, command: '', args: '', env: '', url: '', ...prefill })
    setShowModal(true)
  }

  const openEdit = (srv: McpServer) => {
    setEditServer(srv)
    setForm({
      name: srv.name,
      type: srv.type === 'remote' ? 'http' : srv.type,
      description: srv.description || '',
      enabled: srv.enabled,
      command: srv.command || '',
      args: (srv.args || []).join('\n'),
      env: srv.env ? Object.entries(srv.env).map(([k, v]) => `${k}=${v}`).join('\n') : '',
      url: srv.url || '',
    })
    setShowModal(true)
  }

  const saveServer = async () => {
    const body: Record<string, unknown> = {
      name: form.name, type: form.type,
      description: form.description, enabled: form.enabled,
    }
    if (form.type === 'local') {
      body.command = form.command
      if (form.args.trim()) body.args = form.args.split('\n').map(l => l.trim()).filter(Boolean)
      if (form.env.trim()) {
        const env: Record<string, string> = {}
        form.env.split('\n').forEach(l => {
          const eq = l.indexOf('=')
          if (eq > 0) env[l.slice(0, eq)] = l.slice(eq + 1)
        })
        body.env = env
      }
    } else {
      body.url = form.url
    }

    try {
      if (editServer) {
        await api(`mcp/servers/${encodeURIComponent(editServer.name)}`, { method: 'PUT', body: JSON.stringify(body) })
      } else {
        await api('mcp/servers', { method: 'POST', body: JSON.stringify(body) })
      }
      showToast(editServer ? 'Server updated' : 'Server added', 'success')
      setShowModal(false)
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const configuredNames = new Set(servers.map(s => s.name))

  return (
    <div className="page">
      <Breadcrumb current="MCP Servers" parentPath="/customization" parentLabel="Customization" />
      <div className="page__header">
        <h1>MCP Servers</h1>
        <div className="page__actions">
          <button className="btn btn--primary btn--sm" onClick={() => openAdd()}>Add Server</button>
          <button className="btn btn--ghost btn--sm" onClick={load}>Refresh</button>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab ${tab === 'servers' ? 'tab--active' : ''}`} onClick={() => setTab('servers')}>My Servers</button>
        <button className={`tab ${tab === 'discover' ? 'tab--active' : ''}`} onClick={() => setTab('discover')}>Discover</button>
      </div>

      {tab === 'servers' && (
        <>
          {loading && <div className="spinner" />}
          {!loading && servers.length === 0 && <p className="text-muted">No MCP servers configured</p>}
          <div className="list">
            {servers.map(srv => (
              <div key={srv.name} className={`list-item ${!srv.enabled ? 'list-item--disabled' : ''}`}>
                <span className={`status-indicator ${srv.enabled ? 'status-indicator--ok' : 'status-indicator--err'}`} />
                <div className="list-item__body">
                  <div className="list-item__top">
                    <strong>{srv.name}</strong>
                    <span className="badge">{srv.type}</span>
                    {srv.builtin && <span className="badge badge--muted">built-in</span>}
                    {!srv.enabled && <span className="badge badge--err">disabled</span>}
                  </div>
                  <div className="list-item__desc text-muted">
                    {srv.description || srv.url || `${srv.command || ''} ${(srv.args || []).join(' ')}`}
                  </div>
                </div>
                <div className="list-item__actions">
                  <button className="btn btn--ghost btn--sm" onClick={() => toggleServer(srv.name, !srv.enabled)}>
                    {srv.enabled ? 'Disable' : 'Enable'}
                  </button>
                  {!srv.builtin && (
                    <>
                      <button className="btn btn--ghost btn--sm" onClick={() => openEdit(srv)}>Edit</button>
                      <button className="btn btn--danger btn--sm" onClick={() => removeServer(srv.name)}>Remove</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'discover' && (
        <>
          <div className="search-bar">
            <input
              className="input"
              placeholder="Search MCP servers..."
              value={regQuery}
              onChange={e => setRegQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { setRegPage(1); loadRegistry(1, regQuery) } }}
            />
            <button className="btn btn--secondary btn--sm" onClick={() => { setRegPage(1); loadRegistry(1, regQuery) }}>Search</button>
          </div>
          <div className="grid grid--cards">
            {registry.map(srv => {
              const key = (srv.id || srv.full_name || srv.name || '').replace(/\//g, '-').toLowerCase()
              const added = configuredNames.has(key) || configuredNames.has(srv.name)
              return (
                <div key={srv.id || srv.name} className="card mcp-reg-card">
                  <div className="mcp-reg-card__top">
                    {srv.avatar_url && <img src={srv.avatar_url} alt="" className="mcp-reg-card__avatar" />}
                    <div>
                      <strong>{srv.name}</strong>
                      {srv.stars > 0 && <span className="text-muted"> {srv.stars >= 1000 ? `${(srv.stars/1000).toFixed(1)}k` : srv.stars} stars</span>}
                      {srv.full_name && <div className="text-muted text-sm">{srv.full_name}</div>}
                    </div>
                  </div>
                  {srv.description && <p className="text-sm">{srv.description}</p>}
                  {srv.topics && srv.topics.length > 0 && (
                    <div className="tag-list">
                      {srv.topics.slice(0, 4).map(t => <span key={t} className="tag">{t}</span>)}
                    </div>
                  )}
                  <div className="mcp-reg-card__footer">
                    {srv.license && <span className="text-muted text-sm">{srv.license}</span>}
                    <div className="mcp-reg-card__actions">
                      {srv.url && <a href={srv.url} target="_blank" rel="noopener" className="btn btn--ghost btn--sm">Open</a>}
                      {added ? (
                        <span className="badge badge--ok">Added</span>
                      ) : (
                        <button className="btn btn--primary btn--sm" onClick={() => openAdd({
                          name: key, description: srv.description || '',
                          type: 'local', command: 'npx', args: `-y\n${srv.id || key}`,
                        })}>Add</button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
          <div className="pagination">
            <button className="btn btn--ghost btn--sm" disabled={regPage <= 1} onClick={() => setRegPage(p => p - 1)}>Prev</button>
            <span>Page {regPage}</span>
            <button className="btn btn--ghost btn--sm" disabled={registry.length < 10} onClick={() => setRegPage(p => p + 1)}>Next</button>
          </div>
        </>
      )}

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal__header">
              <h2>{editServer ? 'Edit MCP Server' : 'Add MCP Server'}</h2>
              <button className="btn btn--ghost btn--sm" onClick={() => setShowModal(false)}>&times;</button>
            </div>
            <div className="modal__body">
              <div className="form">
                <div className="form__group">
                  <label className="form__label">Name</label>
                  <input className="input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} disabled={!!editServer} />
                </div>
                <div className="form__group">
                  <label className="form__label">Type</label>
                  <select className="input" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value as typeof form.type }))}>
                    <option value="local">Local (stdio)</option>
                    <option value="http">HTTP (Streamable)</option>
                    <option value="sse">SSE</option>
                  </select>
                </div>
                <div className="form__group">
                  <label className="form__label">Description</label>
                  <input className="input" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
                </div>
                {form.type === 'local' ? (
                  <>
                    <div className="form__group">
                      <label className="form__label">Command</label>
                      <input className="input" value={form.command} onChange={e => setForm(f => ({ ...f, command: e.target.value }))} placeholder="npx" />
                    </div>
                    <div className="form__group">
                      <label className="form__label">Arguments (one per line)</label>
                      <textarea className="input" rows={3} value={form.args} onChange={e => setForm(f => ({ ...f, args: e.target.value }))} />
                    </div>
                    <div className="form__group">
                      <label className="form__label">Environment (KEY=VALUE per line)</label>
                      <textarea className="input" rows={3} value={form.env} onChange={e => setForm(f => ({ ...f, env: e.target.value }))} />
                    </div>
                  </>
                ) : (
                  <div className="form__group">
                    <label className="form__label">URL</label>
                    <input className="input" value={form.url} onChange={e => setForm(f => ({ ...f, url: e.target.value }))} placeholder="https://..." />
                  </div>
                )}
                <label className="form__check">
                  <input type="checkbox" checked={form.enabled} onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))} />
                  Enabled
                </label>
              </div>
            </div>
            <div className="modal__footer">
              <button className="btn btn--secondary" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn--primary" onClick={saveServer}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
