import { useState, useEffect } from 'react'
import { api } from '../api'
import { showToast } from '../components/Toast'
import type { FoundryIQConfig } from '../types'

export function FoundryIQContent() {
  const [config, setConfig] = useState<FoundryIQConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [docCount, setDocCount] = useState<string>('--')
  const [form, setForm] = useState({
    search_endpoint: '', search_api_key: '', index_name: 'polyclaw-memories',
    embedding_endpoint: '', embedding_api_key: '', embedding_model: 'text-embedding-3-large',
    embedding_dimensions: '3072', index_schedule: 'daily', enabled: false,
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [indexing, setIndexing] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const cfg = await api<FoundryIQConfig>('foundry-iq/config')
      setConfig(cfg)
      setForm({
        search_endpoint: cfg.search_endpoint || '',
        search_api_key: '',
        index_name: cfg.index_name || 'polyclaw-memories',
        embedding_endpoint: cfg.embedding_endpoint || '',
        embedding_api_key: '',
        embedding_model: cfg.embedding_model || 'text-embedding-3-large',
        embedding_dimensions: String(cfg.embedding_dimensions || 3072),
        index_schedule: cfg.index_schedule || 'daily',
        enabled: !!cfg.enabled,
      })
      try {
        const stats = await api<{ status: string; document_count?: number; index_missing?: boolean }>('foundry-iq/stats')
        setDocCount(stats.index_missing ? 'No index' : String(stats.document_count || 0))
      } catch { setDocCount('--') }
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const saveConfig = async () => {
    const data: Record<string, unknown> = { ...form, embedding_dimensions: parseInt(form.embedding_dimensions) }
    if (!form.search_api_key) delete data.search_api_key
    if (!form.embedding_api_key) delete data.embedding_api_key
    try {
      await api('foundry-iq/config', { method: 'PUT', body: JSON.stringify(data) })
      await api('foundry-iq/ensure-index', { method: 'POST' })
      showToast('Configuration saved and index created/updated', 'success')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
  }

  const runIndexing = async () => {
    setIndexing(true)
    try {
      const r = await api<{ status: string; indexed: number; total_files: number; total_chunks: number }>('foundry-iq/index', { method: 'POST' })
      showToast(`Indexed ${r.indexed} documents from ${r.total_files} files`, 'success')
      load()
    } catch (e: any) { showToast(e.message, 'error') }
    setIndexing(false)
  }

  const searchMemories = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const r = await api<{ status: string; results: any[] }>('foundry-iq/search', {
        method: 'POST', body: JSON.stringify({ query: searchQuery, top: 5 }),
      })
      setSearchResults(r.results || [])
    } catch (e: any) { showToast(e.message, 'error') }
    setSearching(false)
  }

  if (loading) return <div className="spinner" />

  return (
    <>
      <div className="page__header">
        <h1>Foundry IQ</h1>
        <button className="btn btn--ghost btn--sm" onClick={load}>Refresh</button>
      </div>

      <div className="stats-bar">
        <div className="stat"><span className="stat__value">{config?.enabled ? 'Enabled' : 'Disabled'}</span><span className="stat__label">Status</span></div>
        <div className="stat"><span className="stat__value">{docCount}</span><span className="stat__label">Documents</span></div>
        <div className="stat"><span className="stat__value">{config?.index_schedule || 'daily'}</span><span className="stat__label">Schedule</span></div>
        <div className="stat"><span className="stat__value">{config?.last_indexed_at ? new Date(config.last_indexed_at).toLocaleDateString() : 'Never'}</span><span className="stat__label">Last Indexed</span></div>
      </div>

      {config?.provisioned && (
        <div className="card">
          <h3>Provisioned Resources</h3>
          <div className="detail-grid">
            <div><strong>Resource Group:</strong> {config.resource_group}</div>
            <div><strong>Location:</strong> {config.location}</div>
            <div><strong>Search Service:</strong> {config.search_resource_name}</div>
            <div><strong>OpenAI Account:</strong> {config.openai_resource_name}</div>
          </div>
        </div>
      )}

      <div className="card">
        <h3>Configuration</h3>
        <div className="form">
          <label className="form__check">
            <input type="checkbox" checked={form.enabled} onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))} />
            Enable Foundry IQ
          </label>
          <div className="form__row">
            <div className="form__group">
              <label className="form__label">Search Endpoint</label>
              <input className="input" value={form.search_endpoint} onChange={e => setForm(f => ({ ...f, search_endpoint: e.target.value }))} />
            </div>
            <div className="form__group">
              <label className="form__label">Search API Key</label>
              <input type="password" className="input" value={form.search_api_key} onChange={e => setForm(f => ({ ...f, search_api_key: e.target.value }))} placeholder={config?.search_api_key === '****' ? '(saved)' : ''} />
            </div>
          </div>
          <div className="form__row">
            <div className="form__group">
              <label className="form__label">Embedding Endpoint</label>
              <input className="input" value={form.embedding_endpoint} onChange={e => setForm(f => ({ ...f, embedding_endpoint: e.target.value }))} />
            </div>
            <div className="form__group">
              <label className="form__label">Embedding API Key</label>
              <input type="password" className="input" value={form.embedding_api_key} onChange={e => setForm(f => ({ ...f, embedding_api_key: e.target.value }))} placeholder={config?.embedding_api_key === '****' ? '(saved)' : ''} />
            </div>
          </div>
          <div className="form__row">
            <div className="form__group">
              <label className="form__label">Index Name</label>
              <input className="input" value={form.index_name} onChange={e => setForm(f => ({ ...f, index_name: e.target.value }))} />
            </div>
            <div className="form__group">
              <label className="form__label">Model</label>
              <input className="input" value={form.embedding_model} onChange={e => setForm(f => ({ ...f, embedding_model: e.target.value }))} />
            </div>
            <div className="form__group">
              <label className="form__label">Schedule</label>
              <select className="input" value={form.index_schedule} onChange={e => setForm(f => ({ ...f, index_schedule: e.target.value }))}>
                <option value="daily">Daily</option>
                <option value="hourly">Hourly</option>
                <option value="manual">Manual</option>
              </select>
            </div>
          </div>
          <div className="form__row">
            <button className="btn btn--primary" onClick={saveConfig}>Save & Create Index</button>
            <button className="btn btn--secondary" onClick={runIndexing} disabled={indexing}>{indexing ? 'Indexing...' : 'Run Indexing'}</button>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Search Memories</h3>
        <div className="search-bar">
          <input className="input" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search your memories..." onKeyDown={e => { if (e.key === 'Enter') searchMemories() }} />
          <button className="btn btn--primary btn--sm" onClick={searchMemories} disabled={searching}>{searching ? 'Searching...' : 'Search'}</button>
        </div>
        {searchResults && (
          <div className="mt-2">
            {searchResults.length === 0 && <p className="text-muted">No results found</p>}
            {searchResults.map((doc, i) => (
              <div key={i} className="card card--nested">
                <div className="card__header">
                  <strong>{doc.title}</strong>
                  <span className="text-muted text-sm">Score: {(doc.reranker_score || doc.score || 0).toFixed(2)}</span>
                </div>
                <pre className="text-pre text-sm">{doc.content?.slice(0, 400)}{doc.content?.length > 400 ? '...' : ''}</pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}

export default function FoundryIQ() {
  return <div className="page"><FoundryIQContent /></div>
}
