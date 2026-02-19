import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { showToast } from '../components/Toast'
import { EnvironmentsContent } from './Environments'
import { WorkspaceContent } from './Workspace'
import { FoundryIQContent } from './FoundryIQ'
import type { SetupStatus, SandboxConfig, FoundryIQConfig, NetworkInfo, NetworkEndpoint, NetworkComponent, ResourceAudit, ResourceAuditResponse, ProbeResult, ProbedEndpoint } from '../types'

type Tab = 'overview' | 'preflight' | 'infrastructure' | 'network' | 'sandbox' | 'environments' | 'voice' | 'memory' | 'workspace'

interface PreflightCheck {
  check: string
  ok: boolean
  detail: string
  sub_checks?: { name: string; ok: boolean; detail: string }[]
  endpoints?: { method: string; path: string; status: number | string; ok: boolean }[]
}

interface PreflightResult {
  status: string
  checks: PreflightCheck[]
}

const CHECK_LABELS: Record<string, string> = {
  bot_credentials: 'Bot Credentials',
  jwt_validation: 'JWT Validation',
  tunnel: 'Tunnel',
  tenant_id: 'Tenant ID',
  endpoint_auth: 'Endpoint Auth',
  telegram_security: 'Telegram Security',
  acs_voice: 'ACS / Voice',
  acs_callback_security: 'ACS Callback Security',
}

export default function InfrastructureSettings() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('overview')
  const [status, setStatus] = useState<SetupStatus | null>(null)
  const [sandbox, setSandbox] = useState<SandboxConfig | null>(null)
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [loading, setLoading] = useState<Record<string, boolean>>({})

  const loadAll = useCallback(async () => {
    try {
      const s = await api<SetupStatus>('setup/status')
      setStatus(s)
    } catch { /* ignore */ }
    try {
      const sb = await api<SandboxConfig>('sandbox/config')
      setSandbox(sb)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  const runPreflight = async () => {
    setLoading(p => ({ ...p, preflight: true }))
    try {
      const r = await api<PreflightResult>('setup/preflight')
      setPreflight(r)
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, preflight: false }))
  }

  const startTunnel = async () => {
    setLoading(p => ({ ...p, tunnel: true }))
    try {
      await api('setup/tunnel/start', { method: 'POST' })
      showToast('Tunnel started', 'success')
      loadAll()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, tunnel: false }))
  }

  const stopTunnel = async () => {
    setLoading(p => ({ ...p, tunnel: true }))
    try {
      await api('setup/tunnel/stop', { method: 'POST' })
      showToast('Tunnel stopped', 'success')
      loadAll()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, tunnel: false }))
  }

  const deployInfra = async () => {
    setLoading(p => ({ ...p, deploy: true }))
    try {
      await api('setup/infra/deploy', { method: 'POST' })
      showToast('Infrastructure deployment started', 'success')
      loadAll()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, deploy: false }))
  }

  const decommission = async () => {
    if (!confirm('Decommission infrastructure? This will delete cloud resources.')) return
    setLoading(p => ({ ...p, decommission: true }))
    try {
      await api('setup/infra/decommission', { method: 'POST' })
      showToast('Decommissioning started', 'success')
      loadAll()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, decommission: false }))
  }


  return (
    <div className="page">
      <div className="page__header">
        <h1>Infrastructure</h1>
        {status && (
          <div className="page__status-dots">
            <StatusBadge ok={status.azure?.logged_in} label="Azure" />
            <StatusBadge ok={status.copilot?.authenticated} label="GitHub" />
            <StatusBadge ok={status.tunnel?.active} label="Tunnel" />
            <StatusBadge ok={status.bot_configured} label="Bot" />
          </div>
        )}
      </div>

      <div className="settings__actions">
        <button className="btn btn--outline" onClick={() => navigate('/setup')}>
          Reopen Setup Wizard
        </button>
      </div>

      <div className="tabs">
        {([
          ['overview', 'Overview'],
          ['preflight', 'Preflight'],
          ['infrastructure', 'Provisioning'],
          ['network', 'Network'],
          ['sandbox', 'Sandbox (Experimental)'],
          ['memory', 'Memory / Foundry IQ'],
          ['environments', 'Environments'],
          ['voice', 'Voice'],
          ['workspace', 'Workspace'],
        ] as [Tab, string][]).map(([t, label]) => (
          <button key={t} className={`tab ${tab === t ? 'tab--active' : ''}`} onClick={() => setTab(t)}>
            {label}
          </button>
        ))}
      </div>

      {/* Overview */}
      {tab === 'overview' && status && (
        <div className="card">
          <h3>Platform Status</h3>
          <div className="detail-grid">
            <div><strong>Azure:</strong> {status.azure?.logged_in ? status.azure.subscription || 'Logged in' : 'Not logged in'}</div>
            <div><strong>GitHub Copilot:</strong> {status.copilot?.authenticated ? 'Authenticated' : 'Not authenticated'}</div>
            <div><strong>Tunnel:</strong> {status.tunnel?.active ? status.tunnel.url : 'Inactive'}</div>
            <div><strong>Bot:</strong> {status.bot_configured ? 'Configured' : 'Not configured'}</div>
            <div><strong>Voice:</strong> {status.voice_call_configured ? 'Configured' : 'Not configured'}</div>
          </div>
        </div>
      )}

      {/* Preflight Checks */}
      {tab === 'preflight' && (
        <div className="card">
          <h3>Preflight Checks</h3>
          <p className="text-muted">Security and readiness checks for your deployment.</p>
          <button className="btn btn--primary mt-1" onClick={runPreflight} disabled={loading.preflight}>
            {loading.preflight ? 'Running...' : 'Run Preflight Checks'}
          </button>

          {preflight && (
            <div className="mt-2">
              <span className={`badge ${preflight.status === 'ok' ? 'badge--ok' : 'badge--warn'}`}>
                {preflight.status === 'ok' ? 'All Checks Passed' : 'Warnings'}
              </span>

              <div className="preflight-grid mt-2">
                {preflight.checks.map(c => (
                  <div key={c.check} className="preflight-row">
                    <div className="preflight-row__header">
                      <span className={`status-dot__indicator ${c.ok ? 'status-dot__indicator--ok' : 'status-dot__indicator--err'}`} />
                      <strong>{CHECK_LABELS[c.check] || c.check}</strong>
                      <span className="text-muted ml-2">{c.detail}</span>
                    </div>

                    {c.sub_checks && c.sub_checks.length > 0 && (
                      <details className="preflight-details" open={!c.ok}>
                        <summary>{c.sub_checks.filter(s => s.ok).length}/{c.sub_checks.length} sub-checks passed</summary>
                        {c.sub_checks.map(sc => (
                          <div key={sc.name} className="preflight-row preflight-row--sub">
                            <span className={`status-dot__indicator ${sc.ok ? 'status-dot__indicator--ok' : 'status-dot__indicator--err'}`} />
                            <span>{sc.name}</span>
                            <span className="text-muted ml-2">{sc.detail}</span>
                          </div>
                        ))}
                      </details>
                    )}

                    {c.endpoints && c.endpoints.length > 0 && (
                      <details className="preflight-details" open={!c.ok}>
                        <summary>{c.endpoints.filter(e => e.ok).length}/{c.endpoints.length} endpoints secured</summary>
                        <table className="preflight-table">
                          <thead><tr><th>Method</th><th>Path</th><th>Status</th><th></th></tr></thead>
                          <tbody>
                            {c.endpoints.map(ep => (
                              <tr key={`${ep.method}-${ep.path}`} className={ep.ok ? '' : 'text-err'}>
                                <td>{ep.method}</td>
                                <td>{ep.path}</td>
                                <td>{ep.status}</td>
                                <td>{ep.ok ? 'OK' : 'EXPOSED'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Infrastructure Provisioning */}
      {tab === 'infrastructure' && (
        <div className="infra">
          {/* Tunnel Card */}
          <div className="infra__card">
            <div className="infra__card-header">
              <div className="infra__icon infra__icon--tunnel">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              </div>
              <div className="infra__card-title">
                <h4>Tunnel</h4>
                <p className="text-muted">Cloudflare tunnel for exposing the bot endpoint publicly.</p>
              </div>
              <span className={`badge ${status?.tunnel?.active ? 'badge--ok' : 'badge--muted'}`}>
                {status?.tunnel?.active ? 'Active' : 'Inactive'}
              </span>
            </div>

            {status?.tunnel?.active ? (
              <div className="infra__card-body">
                {status.tunnel?.url && (
                  <div className="infra__url-box">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                    <code>{status.tunnel.url}</code>
                  </div>
                )}
                <button className="btn btn--danger btn--sm" onClick={stopTunnel} disabled={loading.tunnel}>
                  {loading.tunnel ? 'Stopping...' : 'Stop Tunnel'}
                </button>
              </div>
            ) : (
              <div className="infra__card-body">
                <button className="btn btn--primary btn--sm" onClick={startTunnel} disabled={loading.tunnel}>
                  {loading.tunnel ? 'Starting...' : 'Start Tunnel'}
                </button>
              </div>
            )}
          </div>

          {/* Deploy / Decommission Cards */}
          {status?.azure?.logged_in ? (
            <div className="infra__actions-grid">
              <div className="infra__action-card">
                <div className="infra__icon infra__icon--deploy">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m8 17 4 4 4-4"/></svg>
                </div>
                <h4>Deploy Infrastructure</h4>
                <p className="text-muted">Provision Azure Bot Framework resources, register the bot channel, and wire up the messaging endpoint.</p>
                <button className="btn btn--primary mt-1" onClick={deployInfra} disabled={loading.deploy}>
                  {loading.deploy ? 'Deploying...' : 'Deploy'}
                </button>
              </div>

              <div className="infra__action-card infra__action-card--danger">
                <div className="infra__icon infra__icon--decom">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                </div>
                <h4>Decommission</h4>
                <p className="text-muted">Tear down all provisioned Azure resources. This is irreversible and will delete cloud infrastructure.</p>
                <button className="btn btn--danger mt-1" onClick={decommission} disabled={loading.decommission}>
                  {loading.decommission ? 'Decommissioning...' : 'Decommission'}
                </button>
              </div>
            </div>
          ) : (
            <div className="infra__card infra__card--muted">
              <div className="infra__card-header">
                <div className="infra__icon infra__icon--lock">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                </div>
                <div className="infra__card-title">
                  <h4>Azure Login Required</h4>
                  <p className="text-muted">Sign in to Azure to deploy or decommission infrastructure.</p>
                </div>
              </div>
              <div className="infra__card-body">
                <button className="btn btn--primary btn--sm" onClick={() => navigate('/setup')}>
                  Open Setup Wizard
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Network */}
      {tab === 'network' && (
        <NetworkTab tunnelRestricted={!!status?.tunnel?.restricted} onReload={loadAll} />
      )}

      {/* Sandbox */}
      {tab === 'sandbox' && sandbox && (
        <SandboxTab sandbox={sandbox} setSandbox={setSandbox} azureLoggedIn={!!status?.azure?.logged_in} onReload={loadAll} />
      )}

      {/* Environments */}
      {tab === 'environments' && <EnvironmentsContent />}

      {/* Voice */}
      {tab === 'voice' && (
        <VoiceTab status={status} onReload={loadAll} />
      )}

      {/* Memory / Foundry IQ */}
      {tab === 'memory' && (
        <MemoryTab azureLoggedIn={!!status?.azure?.logged_in} />
      )}

      {/* Workspace */}
      {tab === 'workspace' && <WorkspaceContent />}
    </div>
  )
}

function StatusBadge({ ok, label }: { ok?: boolean; label: string }) {
  return (
    <span className={`badge ${ok ? 'badge--ok' : 'badge--err'}`} title={label}>
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Sandbox Tab -- deploy new or connect existing session pool
// ---------------------------------------------------------------------------

type SandboxMode = 'deploy' | 'connect'

function SandboxTab({
  sandbox, setSandbox, azureLoggedIn, onReload,
}: {
  sandbox: SandboxConfig
  setSandbox: React.Dispatch<React.SetStateAction<SandboxConfig | null>>
  azureLoggedIn: boolean
  onReload: () => void
}) {
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [mode, setMode] = useState<SandboxMode>('deploy')
  const [deployLocation, setDeployLocation] = useState('eastus')
  const [deployRg, setDeployRg] = useState('polyclaw-sandbox-rg')

  const saveSandbox = async () => {
    setLoading(p => ({ ...p, save: true }))
    try {
      await api('sandbox/config', {
        method: 'POST',
        body: JSON.stringify({
          enabled: sandbox.enabled,
          sync_data: sandbox.sync_data,
          session_pool_endpoint: sandbox.session_pool_endpoint,
        }),
      })
      showToast('Sandbox config saved', 'success')
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, save: false }))
  }

  const handleProvision = async () => {
    setLoading(p => ({ ...p, deploy: true }))
    try {
      await api('sandbox/provision', {
        method: 'POST',
        body: JSON.stringify({ location: deployLocation, resource_group: deployRg }),
      })
      showToast('Sandbox session pool provisioned', 'success')
      onReload()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, deploy: false }))
  }

  const handleDecommission = async () => {
    if (!confirm('Remove sandbox session pool? This will delete the Azure resource.')) return
    setLoading(p => ({ ...p, decommission: true }))
    try {
      await api('sandbox/provision', { method: 'DELETE' })
      showToast('Sandbox session pool removed', 'success')
      onReload()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, decommission: false }))
  }

  // -- Already provisioned view --
  if (sandbox.is_provisioned) {
    return (
      <div className="voice">
        <div className="voice__status-card">
          <div className="voice__status-header">
            <h3>Agent Sandbox</h3>
            <span className="badge badge--accent">Experimental</span>
            <span className="badge badge--ok">Provisioned</span>
          </div>

          <div className="voice__resource-grid">
            {sandbox.pool_name && (
              <div className="voice__resource-item">
                <label>Session Pool</label>
                <span>{sandbox.pool_name}</span>
              </div>
            )}
            {sandbox.resource_group && (
              <div className="voice__resource-item">
                <label>Resource Group</label>
                <span>{sandbox.resource_group}</span>
              </div>
            )}
            {sandbox.location && (
              <div className="voice__resource-item">
                <label>Location</label>
                <span>{sandbox.location}</span>
              </div>
            )}
          </div>
        </div>

        {/* Configuration */}
        <div className="voice__panel">
          <div className="voice__panel-header">
            <div>
              <h4>Configuration</h4>
              <p className="text-muted">Sandbox settings for code execution.</p>
            </div>
          </div>
          <div className="voice__panel-body">
            <div className="form">
              <label className="form__check">
                <input type="checkbox" checked={sandbox.enabled} onChange={e => setSandbox(s => s ? { ...s, enabled: e.target.checked } : s)} />
                Enable sandbox mode
              </label>
              <label className="form__check">
                <input type="checkbox" checked={sandbox.sync_data !== false} onChange={e => setSandbox(s => s ? { ...s, sync_data: e.target.checked } : s)} />
                Sync data to sandbox
              </label>
              <div className="form__group">
                <label className="form__label">Session Pool Endpoint</label>
                <input className="input" value={sandbox.session_pool_endpoint || ''} onChange={e => setSandbox(s => s ? { ...s, session_pool_endpoint: e.target.value } : s)} />
              </div>
              {sandbox.whitelist && sandbox.whitelist.length > 0 && (
                <div className="mt-1">
                  <label className="form__label">Whitelist</label>
                  <div className="tag-list">
                    {sandbox.whitelist.map(item => <span key={item} className="tag">{item}</span>)}
                  </div>
                </div>
              )}
              <div className="form__actions">
                <button className="btn btn--primary btn--sm" onClick={saveSandbox} disabled={loading.save}>
                  {loading.save ? 'Saving...' : 'Save Configuration'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Decommission */}
        <div className="voice__danger-strip">
          <p>Remove sandbox session pool and clear configuration.</p>
          <button className="btn btn--danger btn--sm" onClick={handleDecommission} disabled={loading.decommission}>
            {loading.decommission ? 'Removing...' : 'Decommission'}
          </button>
        </div>
      </div>
    )
  }

  // -- Not provisioned: setup view --
  return (
    <div className="voice">
      {/* Mode selector bar */}
      <div className="voice__mode-bar">
        <button
          className={`voice__mode-btn${mode === 'deploy' ? ' voice__mode-btn--active' : ''}`}
          onClick={() => setMode('deploy')}
        >
          <div className="voice__mode-icon voice__mode-icon--new">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m8 17 4 4 4-4"/></svg>
          </div>
          <div>
            <h4>Deploy New</h4>
            <p>Provision a new Azure Container Apps session pool</p>
          </div>
        </button>
        <button
          className={`voice__mode-btn${mode === 'connect' ? ' voice__mode-btn--active' : ''}`}
          onClick={() => setMode('connect')}
        >
          <div className="voice__mode-icon voice__mode-icon--link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
          </div>
          <div>
            <h4>Connect Existing</h4>
            <p>Provide an existing session pool endpoint</p>
          </div>
        </button>
      </div>

      {/* Deploy new */}
      {mode === 'deploy' && (
        <div className="voice__panel">
          <div className="voice__panel-header">
            <div>
              <h4>Deploy New Session Pool</h4>
              <p className="text-muted">Creates an Azure Container Apps Dynamic Sessions pool for sandboxed code execution.</p>
            </div>
          </div>
          <div className="voice__panel-body">
            {!azureLoggedIn ? (
              <p className="text-muted">Sign in to Azure first (Overview tab) to provision resources.</p>
            ) : (
              <div className="form">
                <div className="form__row">
                  <div className="form__group">
                    <label className="form__label">Resource Group</label>
                    <input className="input" value={deployRg} onChange={e => setDeployRg(e.target.value)} />
                  </div>
                  <div className="form__group">
                    <label className="form__label">Location</label>
                    <input className="input" value={deployLocation} onChange={e => setDeployLocation(e.target.value)} />
                    <span className="form__hint">Must support Container Apps Dynamic Sessions (e.g. eastus, westeurope).</span>
                  </div>
                </div>
                <div className="form__actions">
                  <button className="btn btn--primary" onClick={handleProvision} disabled={loading.deploy}>
                    {loading.deploy ? 'Provisioning...' : 'Provision Session Pool'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Connect existing */}
      {mode === 'connect' && (
        <div className="voice__panel">
          <div className="voice__panel-header">
            <div>
              <h4>Connect to Existing Session Pool</h4>
              <p className="text-muted">Enter the management endpoint of an existing Azure Container Apps session pool.</p>
            </div>
          </div>
          <div className="voice__panel-body">
            <div className="form">
              <label className="form__check">
                <input type="checkbox" checked={sandbox.enabled} onChange={e => setSandbox(s => s ? { ...s, enabled: e.target.checked } : s)} />
                Enable sandbox mode
              </label>
              <label className="form__check">
                <input type="checkbox" checked={sandbox.sync_data !== false} onChange={e => setSandbox(s => s ? { ...s, sync_data: e.target.checked } : s)} />
                Sync data to sandbox
              </label>
              <div className="form__group">
                <label className="form__label">Session Pool Endpoint</label>
                <input className="input" value={sandbox.session_pool_endpoint || ''} onChange={e => setSandbox(s => s ? { ...s, session_pool_endpoint: e.target.value } : s)} placeholder="https://<region>.dynamicsessions.io/subscriptions/pools/<pool>" />
              </div>
              {sandbox.whitelist && sandbox.whitelist.length > 0 && (
                <div className="mt-1">
                  <label className="form__label">Whitelist</label>
                  <div className="tag-list">
                    {sandbox.whitelist.map(item => <span key={item} className="tag">{item}</span>)}
                  </div>
                </div>
              )}
              <div className="form__actions">
                <button className="btn btn--primary" onClick={saveSandbox} disabled={loading.save}>
                  {loading.save ? 'Saving...' : 'Save Configuration'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Memory / Foundry IQ Tab -- deploy new or connect existing resources
// ---------------------------------------------------------------------------

type MemoryMode = 'deploy' | 'connect'

function MemoryTab({ azureLoggedIn }: { azureLoggedIn: boolean }) {
  const [config, setConfig] = useState<FoundryIQConfig | null>(null)
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [mode, setMode] = useState<MemoryMode>('deploy')
  const [deployLocation, setDeployLocation] = useState('eastus')
  const [deployRg, setDeployRg] = useState('polyclaw-foundryiq-rg')

  const loadConfig = useCallback(async () => {
    try {
      const cfg = await api<FoundryIQConfig>('foundry-iq/config')
      setConfig(cfg)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])

  const handleProvision = async () => {
    setLoading(p => ({ ...p, deploy: true }))
    try {
      await api('foundry-iq/provision', {
        method: 'POST',
        body: JSON.stringify({ location: deployLocation, resource_group: deployRg }),
      })
      showToast('Foundry IQ resources provisioned', 'success')
      await loadConfig()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, deploy: false }))
  }

  const handleDecommission = async () => {
    if (!confirm('Decommission Foundry IQ? This will remove search and OpenAI resources.')) return
    setLoading(p => ({ ...p, decommission: true }))
    try {
      await api('foundry-iq/provision', { method: 'DELETE' })
      showToast('Foundry IQ resources removed', 'success')
      setConfig(null)
      await loadConfig()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, decommission: false }))
  }

  if (!config) return <div className="spinner" />

  // -- Already provisioned or configured --
  if (config.provisioned) {
    return (
      <div className="voice">
        <div className="voice__status-card">
          <div className="voice__status-header">
            <h3>Memory / Foundry IQ</h3>
            <span className="badge badge--ok">Provisioned</span>
          </div>
          <div className="voice__resource-grid">
            {config.search_resource_name && (
              <div className="voice__resource-item">
                <label>Search Service</label>
                <span>{config.search_resource_name}</span>
              </div>
            )}
            {config.openai_resource_name && (
              <div className="voice__resource-item">
                <label>OpenAI Account</label>
                <span>{config.openai_resource_name}</span>
              </div>
            )}
            {config.resource_group && (
              <div className="voice__resource-item">
                <label>Resource Group</label>
                <span>{config.resource_group}</span>
              </div>
            )}
            {config.location && (
              <div className="voice__resource-item">
                <label>Location</label>
                <span>{config.location}</span>
              </div>
            )}
          </div>
        </div>

        {/* Inline the full configuration + search UI */}
        <FoundryIQContent />

        {/* Decommission */}
        <div className="voice__danger-strip">
          <p>Remove all Foundry IQ Azure resources and clear configuration.</p>
          <button className="btn btn--danger btn--sm" onClick={handleDecommission} disabled={loading.decommission}>
            {loading.decommission ? 'Decommissioning...' : 'Decommission'}
          </button>
        </div>
      </div>
    )
  }

  // -- Not provisioned: setup view --
  return (
    <div className="voice">
      {/* Mode selector bar */}
      <div className="voice__mode-bar">
        <button
          className={`voice__mode-btn${mode === 'deploy' ? ' voice__mode-btn--active' : ''}`}
          onClick={() => setMode('deploy')}
        >
          <div className="voice__mode-icon voice__mode-icon--new">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m8 17 4 4 4-4"/></svg>
          </div>
          <div>
            <h4>Deploy New</h4>
            <p>Provision Azure AI Search + OpenAI for memory indexing</p>
          </div>
        </button>
        <button
          className={`voice__mode-btn${mode === 'connect' ? ' voice__mode-btn--active' : ''}`}
          onClick={() => setMode('connect')}
        >
          <div className="voice__mode-icon voice__mode-icon--link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
          </div>
          <div>
            <h4>Connect Existing</h4>
            <p>Provide endpoints for existing search and embedding resources</p>
          </div>
        </button>
      </div>

      {/* Deploy new */}
      {mode === 'deploy' && (
        <div className="voice__panel">
          <div className="voice__panel-header">
            <div>
              <h4>Deploy New Foundry IQ Resources</h4>
              <p className="text-muted">Creates a resource group with Azure AI Search (Basic) and Azure OpenAI with a text-embedding-3-large deployment.</p>
            </div>
          </div>
          <div className="voice__panel-body">
            {!azureLoggedIn ? (
              <p className="text-muted">Sign in to Azure first (Overview tab) to provision resources.</p>
            ) : (
              <div className="form">
                <div className="form__row">
                  <div className="form__group">
                    <label className="form__label">Resource Group</label>
                    <input className="input" value={deployRg} onChange={e => setDeployRg(e.target.value)} />
                  </div>
                  <div className="form__group">
                    <label className="form__label">Location</label>
                    <input className="input" value={deployLocation} onChange={e => setDeployLocation(e.target.value)} />
                    <span className="form__hint">Must support Azure OpenAI embeddings (e.g. eastus, swedencentral).</span>
                  </div>
                </div>
                <div className="form__actions">
                  <button className="btn btn--primary" onClick={handleProvision} disabled={loading.deploy}>
                    {loading.deploy ? 'Provisioning...' : 'Deploy Foundry IQ'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Connect existing */}
      {mode === 'connect' && <FoundryIQContent />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Voice Tab -- deploy new or connect to existing ACS + AOAI resources
// ---------------------------------------------------------------------------

interface AzureResource { name: string; resource_group: string; location: string }
interface AoaiDeployment { deployment_name: string; model_name: string; model_version: string; is_realtime?: boolean }
interface VoiceConfig {
  acs_resource_name?: string
  acs_connection_string?: string
  acs_source_number?: string
  voice_target_number?: string
  azure_openai_resource_name?: string
  azure_openai_endpoint?: string
  azure_openai_realtime_deployment?: string
  voice_resource_group?: string
  resource_group?: string
  location?: string
  portal_phone_url?: string
}

type VoiceMode = 'deploy' | 'connect'

function VoiceTab({ status, onReload }: { status: SetupStatus | null; onReload: () => void }) {
  const [voiceConfig, setVoiceConfig] = useState<VoiceConfig | null>(null)
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [mode, setMode] = useState<VoiceMode>('connect')

  // Connect-existing state
  const [aoaiList, setAoaiList] = useState<AzureResource[]>([])
  const [acsList, setAcsList] = useState<AzureResource[]>([])
  const [aoaiDeployments, setAoaiDeployments] = useState<AoaiDeployment[]>([])
  const [selectedAoai, setSelectedAoai] = useState<AzureResource | null>(null)
  const [selectedAoaiDep, setSelectedAoaiDep] = useState('')
  const [selectedAcs, setSelectedAcs] = useState<AzureResource | null>(null)
  const [skipAcs, setSkipAcs] = useState(false)
  const [acsPhones, setAcsPhones] = useState<string[]>([])
  const [phoneNumber, setPhoneNumber] = useState('')
  const [connectTargetPhone, setConnectTargetPhone] = useState('')

  // Deploy-new state
  const [deployLocation, setDeployLocation] = useState('swedencentral')
  const [deployRg, setDeployRg] = useState('polyclaw-voice-rg')

  // Phone config state
  const [sourcePhone, setSourcePhone] = useState('')
  const [targetPhone, setTargetPhone] = useState('')
  const [configuredPhones, setConfiguredPhones] = useState<string[]>([])

  const loadConfig = useCallback(async () => {
    try {
      const vc = await api<VoiceConfig>('setup/voice/config')
      setVoiceConfig(vc)
      if (vc.acs_source_number) setSourcePhone(vc.acs_source_number)
      if (vc.voice_target_number) setTargetPhone(vc.voice_target_number)
      // Load purchased phones for the configured ACS resource
      if (vc.acs_resource_name) {
        const rg = vc.voice_resource_group || vc.resource_group || ''
        if (rg) {
          try {
            const phones = await api<{ phone_number: string }[]>(
              `setup/voice/acs/phones?name=${encodeURIComponent(vc.acs_resource_name)}&resource_group=${encodeURIComponent(rg)}`
            )
            setConfiguredPhones(phones.map(p => p.phone_number))
          } catch { /* ignore */ }
        }
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])

  const discoverResources = async () => {
    setLoading(p => ({ ...p, discover: true }))
    try {
      const [aoai, acs] = await Promise.all([
        api<AzureResource[]>('setup/voice/aoai/list'),
        api<AzureResource[]>('setup/voice/acs/list'),
      ])
      setAoaiList(aoai)
      setAcsList(acs)
      if (aoai.length > 0 && !selectedAoai) {
        setSelectedAoai(aoai[0])
        loadDeployments(aoai[0])
      }
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, discover: false }))
  }

  const loadDeployments = async (resource: AzureResource) => {
    setAoaiDeployments([])
    setSelectedAoaiDep('')
    try {
      const deps = await api<AoaiDeployment[]>(
        `setup/voice/aoai/deployments?name=${encodeURIComponent(resource.name)}&resource_group=${encodeURIComponent(resource.resource_group)}`
      )
      setAoaiDeployments(deps)
      const realtime = deps.find(d => {
        const n = d.model_name || ''
        return n.includes('realtime')
      })
      if (realtime) setSelectedAoaiDep(realtime.deployment_name)
      else if (deps.length > 0) setSelectedAoaiDep(deps[0].deployment_name)
    } catch { /* ignore */ }
  }

  const handleSelectAoai = (idx: number) => {
    const resource = aoaiList[idx]
    setSelectedAoai(resource)
    loadDeployments(resource)
  }

  const loadAcsPhones = async (resource: AzureResource) => {
    setAcsPhones([])
    try {
      const phones = await api<{ phone_number: string }[]>(
        `setup/voice/acs/phones?name=${encodeURIComponent(resource.name)}&resource_group=${encodeURIComponent(resource.resource_group)}`
      )
      setAcsPhones(phones.map(p => p.phone_number))
      if (phones.length > 0 && !phoneNumber) setPhoneNumber(phones[0].phone_number)
    } catch { /* ignore */ }
  }

  const handleSelectAcs = (idx: number) => {
    const resource = acsList[idx]
    setSelectedAcs(resource)
    if (resource) loadAcsPhones(resource)
    else { setAcsPhones([]); setPhoneNumber('') }
  }

  const handleConnectExisting = async () => {
    if (!selectedAoai) { showToast('Select an Azure OpenAI resource', 'error'); return }
    if (!selectedAoaiDep) { showToast('Select a deployment', 'error'); return }
    setLoading(p => ({ ...p, connect: true }))
    try {
      const body: Record<string, string> = {
        aoai_name: selectedAoai.name,
        aoai_resource_group: selectedAoai.resource_group,
        aoai_deployment: selectedAoaiDep,
      }
      if (!skipAcs && selectedAcs) {
        body.acs_name = selectedAcs.name
        body.acs_resource_group = selectedAcs.resource_group
      }
      if (phoneNumber) body.phone_number = phoneNumber
      if (connectTargetPhone) body.target_number = connectTargetPhone
      await api('setup/voice/connect', { method: 'POST', body: JSON.stringify(body) })
      showToast('Connected to existing resources', 'success')
      await loadConfig()
      onReload()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, connect: false }))
  }

  const handleDeployNew = async () => {
    setLoading(p => ({ ...p, deploy: true }))
    try {
      await api('setup/voice/deploy', {
        method: 'POST',
        body: JSON.stringify({ location: deployLocation, voice_resource_group: deployRg }),
      })
      showToast('Voice infrastructure deployed', 'success')
      await loadConfig()
      onReload()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, deploy: false }))
  }

  const handleSavePhone = async () => {
    setLoading(p => ({ ...p, phone: true }))
    try {
      const body: Record<string, string> = {}
      if (sourcePhone) body.phone_number = sourcePhone
      if (targetPhone) body.target_number = targetPhone
      await api('setup/voice/phone', { method: 'POST', body: JSON.stringify(body) })
      showToast('Phone number(s) saved', 'success')
      await loadConfig()
      onReload()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, phone: false }))
  }

  const handleDecommission = async () => {
    if (!confirm('Decommission voice infrastructure? This will remove ACS and AOAI resources.')) return
    setLoading(p => ({ ...p, decommission: true }))
    try {
      await api('setup/voice/decommission', { method: 'POST' })
      showToast('Voice infrastructure decommissioned', 'success')
      setVoiceConfig(null)
      onReload()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, decommission: false }))
  }

  const configured = !!voiceConfig?.acs_resource_name || status?.voice_call_configured

  // -- Already configured view --
  if (configured && voiceConfig) {
    return (
      <div className="voice">
        <div className="voice__status-card">
          <div className="voice__status-header">
            <h3>Voice Call Infrastructure</h3>
            <span className="badge badge--ok">Configured</span>
          </div>

          <div className="voice__resource-grid">
            {voiceConfig.acs_resource_name && (
              <div className="voice__resource-item">
                <label>ACS Resource</label>
                <span>{voiceConfig.acs_resource_name}</span>
              </div>
            )}
            {voiceConfig.azure_openai_resource_name && (
              <div className="voice__resource-item">
                <label>Azure OpenAI</label>
                <span>{voiceConfig.azure_openai_resource_name}</span>
              </div>
            )}
            {voiceConfig.azure_openai_realtime_deployment && (
              <div className="voice__resource-item">
                <label>Deployment</label>
                <span>{voiceConfig.azure_openai_realtime_deployment}</span>
              </div>
            )}
            {(voiceConfig.voice_resource_group || voiceConfig.resource_group) && (
              <div className="voice__resource-item">
                <label>Resource Group</label>
                <span>{voiceConfig.voice_resource_group || voiceConfig.resource_group}</span>
              </div>
            )}
            {voiceConfig.location && (
              <div className="voice__resource-item">
                <label>Location</label>
                <span>{voiceConfig.location}</span>
              </div>
            )}
            {voiceConfig.acs_source_number && (
              <div className="voice__resource-item">
                <label>Source Phone</label>
                <span>{voiceConfig.acs_source_number}</span>
              </div>
            )}
            {voiceConfig.voice_target_number && (
              <div className="voice__resource-item">
                <label>Target Phone</label>
                <span>{voiceConfig.voice_target_number}</span>
              </div>
            )}
          </div>

          {voiceConfig.portal_phone_url && (
            <a href={voiceConfig.portal_phone_url} target="_blank" rel="noopener" className="btn btn--outline btn--sm">
              Manage Phone Numbers in Azure Portal
            </a>
          )}
        </div>

        {/* Phone number config */}
        <div className="voice__panel">
          <div className="voice__panel-header">
            <div>
              <h4>Phone Numbers</h4>
              <p className="text-muted">ACS source number and your phone number (the only number the AI is allowed to call).</p>
            </div>
          </div>
          <div className="voice__panel-body">
            <div className="form">
              <div className="form__row">
                <div className="form__group">
                  <label className="form__label">ACS Source Number</label>
                  {configuredPhones.length > 0 ? (
                    <select className="input" value={sourcePhone} onChange={e => setSourcePhone(e.target.value)}>
                      <option value="">Select a purchased number...</option>
                      {configuredPhones.map(p => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  ) : (
                    <input className="input" value={sourcePhone} onChange={e => setSourcePhone(e.target.value)} placeholder="+14155551234" />
                  )}
                  <span className="form__hint">The phone number purchased in ACS that the AI calls from.</span>
                </div>
                <div className="form__group">
                  <label className="form__label">Your Phone Number</label>
                  <input className="input" value={targetPhone} onChange={e => setTargetPhone(e.target.value)} placeholder="+41781234567" />
                  <span className="form__hint">Your personal number. The AI is only allowed to call this number.</span>
                </div>
              </div>
              <div className="form__actions">
                <button className="btn btn--primary btn--sm" onClick={handleSavePhone} disabled={loading.phone || (!sourcePhone && !targetPhone)}>
                  {loading.phone ? 'Saving...' : 'Save Phone Numbers'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Decommission */}
        <div className="voice__danger-strip">
          <p>Remove voice infrastructure and clear all configuration.</p>
          <button className="btn btn--danger btn--sm" onClick={handleDecommission} disabled={loading.decommission}>
            {loading.decommission ? 'Decommissioning...' : 'Decommission'}
          </button>
        </div>
      </div>
    )
  }

  // -- Not configured: setup view --
  return (
    <div className="voice">
      {/* Mode selector bar */}
      <div className="voice__mode-bar">
        <button
          className={`voice__mode-btn${mode === 'connect' ? ' voice__mode-btn--active' : ''}`}
          onClick={() => { setMode('connect'); discoverResources() }}
        >
          <div className="voice__mode-icon voice__mode-icon--link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
          </div>
          <div>
            <h4>Connect Existing</h4>
            <p>Link to resources already in your subscription</p>
          </div>
        </button>
        <button
          className={`voice__mode-btn${mode === 'deploy' ? ' voice__mode-btn--active' : ''}`}
          onClick={() => setMode('deploy')}
        >
          <div className="voice__mode-icon voice__mode-icon--new">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m8 17 4 4 4-4"/></svg>
          </div>
          <div>
            <h4>Deploy New</h4>
            <p>Provision new ACS + Azure OpenAI resources</p>
          </div>
        </button>
      </div>

      {/* Connect existing form */}
      {mode === 'connect' && (
        <div className="voice__panel">
          <div className="voice__panel-header">
            <div>
              <h4>Connect to Existing Resources</h4>
              <p className="text-muted">Select Azure OpenAI and optionally ACS resources from your subscription.</p>
            </div>
            <button className="btn btn--outline btn--sm" onClick={discoverResources} disabled={loading.discover}>
              {loading.discover ? 'Scanning...' : 'Refresh'}
            </button>
          </div>
          <div className="voice__panel-body">
            <div className="form">
              <div className="voice__section-label">Azure OpenAI</div>

              <div className="form__group">
                <label className="form__label">Resource</label>
                {aoaiList.length === 0 ? (
                  <p className="text-muted" style={{ fontSize: 13 }}>
                    {loading.discover ? 'Scanning subscription...' : 'No Azure OpenAI resources found. Click Refresh or use Deploy New.'}
                  </p>
                ) : (
                  <select
                    className="input"
                    value={selectedAoai ? aoaiList.indexOf(selectedAoai) : ''}
                    onChange={e => handleSelectAoai(Number(e.target.value))}
                  >
                    {aoaiList.map((r, i) => (
                      <option key={r.name} value={i}>{r.name} ({r.resource_group} / {r.location})</option>
                    ))}
                  </select>
                )}
              </div>

              {selectedAoai && (
                <div className="form__group">
                  <label className="form__label">Realtime Deployment</label>
                  {aoaiDeployments.length === 0 ? (
                    <p className="text-muted" style={{ fontSize: 13 }}>No deployments found. Deploy a realtime model (e.g. gpt-realtime-mini) first.</p>
                  ) : (
                    <select
                      className="input"
                      value={selectedAoaiDep}
                      onChange={e => setSelectedAoaiDep(e.target.value)}
                    >
                      {aoaiDeployments.map(d => (
                        <option key={d.deployment_name} value={d.deployment_name}>
                          {d.deployment_name} ({d.model_name} {d.model_version})
                        </option>
                      ))}
                    </select>
                  )}
                  <span className="form__hint">Requires a realtime-capable model (gpt-realtime-mini, gpt-4o-realtime-preview).</span>
                </div>
              )}

              <div className="voice__section-label">Communication Services</div>

              <div className="form__group">
                <label className="form__check">
                  <input type="checkbox" checked={skipAcs} onChange={e => { setSkipAcs(e.target.checked); if (e.target.checked) setSelectedAcs(null) }} />
                  Create a new ACS resource automatically
                </label>
                {!skipAcs && (
                  acsList.length === 0 ? (
                    <p className="text-muted" style={{ fontSize: 13 }}>No ACS resources found. Enable the checkbox above to create one.</p>
                  ) : (
                    <select
                      className="input"
                      value={selectedAcs ? acsList.indexOf(selectedAcs) : ''}
                      onChange={e => handleSelectAcs(Number(e.target.value))}
                    >
                      <option value="">Select an ACS resource...</option>
                      {acsList.map((r, i) => (
                        <option key={r.name} value={i}>{r.name} ({r.resource_group})</option>
                      ))}
                    </select>
                  )
                )}
              </div>

              <div className="voice__section-label">Phone Numbers</div>

              <div className="form__group">
                <label className="form__label">ACS Source Number</label>
                {acsPhones.length > 0 ? (
                  <select className="input" value={phoneNumber} onChange={e => setPhoneNumber(e.target.value)}>
                    <option value="">Select a purchased number...</option>
                    {acsPhones.map(p => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                ) : (
                  <input className="input" value={phoneNumber} onChange={e => setPhoneNumber(e.target.value)} placeholder="+14155551234" />
                )}
                <span className="form__hint">{selectedAcs && acsPhones.length === 0 ? 'No purchased numbers found on this ACS resource. You can add one later.' : 'The number the AI calls from. Can be configured later.'}</span>
              </div>

              <div className="form__group">
                <label className="form__label">Your Phone Number</label>
                <input className="input" value={connectTargetPhone} onChange={e => setConnectTargetPhone(e.target.value)} placeholder="+41781234567" />
                <span className="form__hint">Your personal number. The AI is only allowed to call this number.</span>
              </div>

              <div className="form__actions">
                <button
                  className="btn btn--primary"
                  onClick={handleConnectExisting}
                  disabled={loading.connect || !selectedAoai || !selectedAoaiDep}
                >
                  {loading.connect ? 'Connecting...' : 'Connect Resources'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Deploy new form */}
      {mode === 'deploy' && (
        <div className="voice__panel">
          <div className="voice__panel-header">
            <div>
              <h4>Deploy New Voice Infrastructure</h4>
              <p className="text-muted">Creates a resource group with ACS and Azure OpenAI (gpt-realtime-mini).</p>
            </div>
          </div>
          <div className="voice__panel-body">
            <div className="form">
              <div className="form__row">
                <div className="form__group">
                  <label className="form__label">Resource Group</label>
                  <input className="input" value={deployRg} onChange={e => setDeployRg(e.target.value)} />
                </div>
                <div className="form__group">
                  <label className="form__label">Location</label>
                  <input className="input" value={deployLocation} onChange={e => setDeployLocation(e.target.value)} />
                  <span className="form__hint">Must support Azure OpenAI realtime models (e.g. swedencentral, eastus2).</span>
                </div>
              </div>
              <div className="form__actions">
                <button className="btn btn--primary" onClick={handleDeployNew} disabled={loading.deploy}>
                  {loading.deploy ? 'Deploying...' : 'Deploy Voice Infrastructure'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Network Tab -- network topology, tunnel exposure, and endpoint listing
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  bot: 'Bot / Messaging',
  voice: 'Voice / ACS',
  chat: 'Chat / Models',
  setup: 'Setup / Config',
  admin: 'Admin API',
  'foundry-iq': 'Foundry IQ',
  sandbox: 'Sandbox',
  network: 'Network',
  health: 'Health',
  frontend: 'Frontend',
}

const CATEGORY_ORDER = ['bot', 'voice', 'chat', 'admin', 'setup', 'foundry-iq', 'sandbox', 'network', 'health', 'frontend']

const MODE_LABELS: Record<string, string> = {
  local: 'Local Development',
  docker: 'Docker Container',
  aca: 'Azure Container Apps',
}

const COMPONENT_ICONS: Record<string, string> = {
  ai: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
  tunnel: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  bot: 'M12 8V4H8',
  communication: 'M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.362 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.338 1.85.573 2.81.7A2 2 0 0 1 22 16.92z',
  search: 'M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM21 21l-4.35-4.35',
  storage: 'M22 12H2M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z',
}

const RESOURCE_AUDIT_ICONS: Record<string, string> = {
  storage: 'M22 12H2M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z',
  keyvault: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  ai: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
  search: 'M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM21 21l-4.35-4.35',
  acr: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z',
  sandbox: 'M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7',
  communication: 'M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.362 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.338 1.85.573 2.81.7A2 2 0 0 1 22 16.92z',
}

function NetworkTab({ tunnelRestricted, onReload }: { tunnelRestricted: boolean; onReload: () => void }) {
  const [info, setInfo] = useState<NetworkInfo | null>(null)
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [filter, setFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [showTunnelOnly, setShowTunnelOnly] = useState(false)
  const [auditResources, setAuditResources] = useState<ResourceAudit[]>([])
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditLoaded, setAuditLoaded] = useState(false)
  const [probe, setProbe] = useState<ProbeResult | null>(null)
  const [probing, setProbing] = useState(false)

  const loadInfo = useCallback(async () => {
    try {
      const data = await api<NetworkInfo>('network/info')
      setInfo(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadInfo() }, [loadInfo])

  const runProbe = useCallback(async () => {
    setProbing(true)
    try {
      const data = await api<ProbeResult>('network/probe')
      setProbe(data)
    } catch { /* ignore */ }
    setProbing(false)
  }, [])

  useEffect(() => { runProbe() }, [runProbe])

  const loadAudit = async () => {
    setAuditLoading(true)
    try {
      const data = await api<ResourceAuditResponse>('network/resource-audit')
      setAuditResources(data.resources || [])
      setAuditLoaded(true)
    } catch { /* ignore */ }
    setAuditLoading(false)
  }

  const toggleTunnelRestriction = async () => {
    const newState = !info?.tunnel.restricted
    setLoading(p => ({ ...p, restrict: true }))
    try {
      await api('setup/tunnel/restrict', {
        method: 'POST',
        body: JSON.stringify({ restricted: newState }),
      })
      showToast(
        newState
          ? 'Tunnel restricted: only bot + ACS endpoints exposed'
          : 'Tunnel unrestricted: all endpoints exposed',
        'success',
      )
      await loadInfo()
      onReload()
    } catch (e: any) { showToast(e.message, 'error') }
    setLoading(p => ({ ...p, restrict: false }))
  }

  if (!info) return <div className="spinner" />

  // Use probed endpoint data when available, fall back to static info
  const endpointSource: (NetworkEndpoint | ProbedEndpoint)[] = probe ? probe.endpoints : info.endpoints

  // Group endpoints by category
  const grouped: Record<string, (NetworkEndpoint | ProbedEndpoint)[]> = {}
  for (const ep of endpointSource) {
    if (showTunnelOnly && !ep.tunnel_exposed) continue
    if (filter && !ep.path.toLowerCase().includes(filter.toLowerCase()) && !ep.method.toLowerCase().includes(filter.toLowerCase())) continue
    if (categoryFilter && ep.category !== categoryFilter) continue
    if (!grouped[ep.category]) grouped[ep.category] = []
    grouped[ep.category].push(ep)
  }

  const sortedCategories = CATEGORY_ORDER.filter(c => grouped[c])
  const extraCategories = Object.keys(grouped).filter(c => !CATEGORY_ORDER.includes(c))
  const allCategories = [...sortedCategories, ...extraCategories]

  const totalEndpoints = endpointSource.length
  const tunnelExposed = endpointSource.filter(e => e.tunnel_exposed).length

  return (
    <div className="network">
      {/* Deploy mode & topology card */}
      <div className="network__topo-card">
        <div className="network__topo-header">
          <h3>Network Topology</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button className="btn btn--secondary btn--sm" onClick={runProbe} disabled={probing} title="Re-probe all endpoints">
              {probing ? 'Probing...' : 'Re-probe'}
            </button>
            <span className={`badge ${info.deploy_mode === 'aca' ? 'badge--ok' : info.deploy_mode === 'docker' ? 'badge--warn' : 'badge--muted'}`}>
              {MODE_LABELS[info.deploy_mode] || info.deploy_mode}
            </span>
          </div>
        </div>

        <div className="network__topo-grid">
          {/* The Server */}
          <div className="network__topo-node network__topo-node--server">
            <div className="network__topo-node-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
                <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
                <line x1="6" y1="6" x2="6.01" y2="6" />
                <line x1="6" y1="18" x2="6.01" y2="18" />
              </svg>
            </div>
            <div className="network__topo-node-label">
              <strong>Polyclaw Server</strong>
              <span>Port {info.admin_port}</span>
              {info.deploy_mode === 'docker' && <span className="text-muted">Container</span>}
              {info.deploy_mode === 'aca' && <span className="text-muted">Azure Container Apps</span>}
              {info.deploy_mode === 'local' && <span className="text-muted">localhost</span>}
              <span className="network__topo-count">
                {probe ? `${probe.counts.total} endpoints` : probing ? '...' : ''}
              </span>
            </div>
          </div>

          {/* Arrow */}
          <div className="network__topo-arrow">
            <svg width="40" height="24" viewBox="0 0 40 24">
              <line x1="0" y1="12" x2="32" y2="12" stroke="var(--text-3)" strokeWidth="2" />
              <polygon points="32,6 40,12 32,18" fill="var(--text-3)" />
            </svg>
          </div>

          {/* Tunnel */}
          <div className={`network__topo-node ${info.tunnel.active ? 'network__topo-node--active' : 'network__topo-node--inactive'}`}>
            <div className="network__topo-node-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div className="network__topo-node-label">
              <strong>Cloudflare Tunnel</strong>
              {info.tunnel.active ? (
                <>
                  <span className="network__topo-url">{info.tunnel.url}</span>
                  <span className={info.tunnel.restricted ? 'text-warn' : 'text-ok'}>
                    {info.tunnel.restricted ? 'Restricted' : 'Full Access'}
                  </span>
                </>
              ) : (
                <span className="text-muted">Inactive</span>
              )}
              <span className="network__topo-count">
                {probe ? `${probe.counts.tunnel_accessible} exposed` : probing ? '...' : ''}
              </span>
            </div>
          </div>

          {/* Arrow */}
          <div className="network__topo-arrow">
            <svg width="40" height="24" viewBox="0 0 40 24">
              <line x1="0" y1="12" x2="32" y2="12" stroke="var(--text-3)" strokeWidth="2" />
              <polygon points="32,6 40,12 32,18" fill="var(--text-3)" />
            </svg>
          </div>

          {/* Internet / Azure */}
          <div className="network__topo-node network__topo-node--cloud">
            <div className="network__topo-node-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
              </svg>
            </div>
            <div className="network__topo-node-label">
              <strong>{info.deploy_mode === 'aca' ? 'Azure' : 'Internet'}</strong>
              <span className="text-muted">Bot Service, Teams, Telegram</span>
              <span className="network__topo-count">
                {probe ? `${probe.counts.public_no_auth} public` : probing ? '...' : ''}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Connected components */}
      <div className="network__components">
        <h4>Connected Components</h4>
        <div className="network__comp-grid">
          {info.components.map(comp => (
            <div key={comp.name} className={`network__comp-item ${comp.status === 'active' || comp.status === 'configured' ? '' : 'network__comp-item--inactive'}`}>
              <div className="network__comp-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d={COMPONENT_ICONS[comp.type] || COMPONENT_ICONS.storage} />
                </svg>
              </div>
              <div className="network__comp-info">
                <strong>{comp.name}</strong>
                {comp.endpoint && <span className="network__comp-detail">{comp.endpoint}</span>}
                {comp.url && <span className="network__comp-detail">{comp.url}</span>}
                {comp.model && <span className="network__comp-detail">Model: {comp.model}</span>}
                {comp.deployment && <span className="network__comp-detail">Deployment: {comp.deployment}</span>}
                {comp.source_number && <span className="network__comp-detail">Number: {comp.source_number}</span>}
                {comp.path && <span className="network__comp-detail">{comp.path}</span>}
              </div>
              <span className={`badge ${comp.status === 'active' || comp.status === 'configured' ? 'badge--ok' : 'badge--muted'}`}>
                {comp.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Tunnel exposure mode */}
      <div className="network__exposure">
        <div className="network__exposure-header">
          <div>
            <h4>Tunnel Exposure Mode</h4>
            <p className="text-muted">
              {info.tunnel.restricted
                ? 'Restricted mode: only bot messaging and ACS callback endpoints are exposed through the tunnel. All other endpoints are accessible only on the local network.'
                : 'Full access mode: all endpoints are exposed through the tunnel. Switch to restricted mode to limit tunnel exposure to only bot and ACS endpoints.'}
            </p>
          </div>
        </div>

        <div className="network__exposure-controls">
          <div className="network__exposure-toggle">
            <button
              className={`network__mode-btn ${!info.tunnel.restricted ? 'network__mode-btn--active network__mode-btn--full' : ''}`}
              onClick={() => info.tunnel.restricted && toggleTunnelRestriction()}
              disabled={loading.restrict || !info.tunnel.active}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /></svg>
              Full Access
            </button>
            <button
              className={`network__mode-btn ${info.tunnel.restricted ? 'network__mode-btn--active network__mode-btn--restricted' : ''}`}
              onClick={() => !info.tunnel.restricted && toggleTunnelRestriction()}
              disabled={loading.restrict || !info.tunnel.active}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
              Restricted
            </button>
          </div>
          {!info.tunnel.active && (
            <p className="text-muted" style={{ fontSize: 12 }}>Start the tunnel first to change exposure mode.</p>
          )}
        </div>

        <div className="network__exposure-stats">
          <div className="network__stat">
            <span className="network__stat-value">{probe ? probe.counts.total : totalEndpoints}</span>
            <span className="network__stat-label">Total Endpoints</span>
          </div>
          <div className="network__stat">
            <span className="network__stat-value">{probe?.counts.auth_types?.admin_key ?? '--'}</span>
            <span className="network__stat-label">Admin Key</span>
          </div>
          <div className="network__stat">
            <span className="network__stat-value">{probe?.counts.auth_types?.bot_jwt ?? '--'}</span>
            <span className="network__stat-label">Bot JWT</span>
          </div>
          <div className="network__stat">
            <span className="network__stat-value">{probe?.counts.auth_types?.acs_token ?? '--'}</span>
            <span className="network__stat-label">ACS Token</span>
          </div>
          <div className="network__stat">
            <span className="network__stat-value">{probe?.counts.auth_types?.open ?? '--'}</span>
            <span className="network__stat-label">Open</span>
          </div>
          <div className="network__stat">
            <span className="network__stat-value">{probe ? probe.counts.tunnel_accessible : tunnelExposed}</span>
            <span className="network__stat-label">Tunnel-Exposed</span>
          </div>
          <div className="network__stat">
            <span className="network__stat-value">{probe ? probe.counts.tunnel_blocked : totalEndpoints - tunnelExposed}</span>
            <span className="network__stat-label">Tunnel-Blocked</span>
          </div>
        </div>
        {probe && probe.counts.framework_auth_fail > 0 && (
          <p className="text-warn" style={{ fontSize: 12, marginTop: 8 }}>
            {probe.counts.framework_auth_fail} bot/ACS endpoint(s) accepted unauthenticated POST requests. Check that Bot Framework credentials and ACS callback token are configured.
          </p>
        )}
        {probe && !probe.tunnel_restricted_during_probe && (
          <p className="text-muted" style={{ fontSize: 12, marginTop: 8 }}>
            Tunnel restriction was off during probe -- all endpoints appear tunnel-accessible. Switch to restricted mode and re-probe to see which endpoints would be blocked.
          </p>
        )}
      </div>

      {/* Resource Network Security */}
      <div className="network__resource-audit">
        <div className="network__resource-audit-header">
          <div>
            <h4>Resource Network Security</h4>
            <p className="text-muted">Network configuration of Azure resources across all resource groups: firewall rules, allowed IPs, public access, private endpoints.</p>
          </div>
          <button className="btn btn--secondary btn--sm" onClick={loadAudit} disabled={auditLoading}>
            {auditLoading ? 'Scanning...' : auditLoaded ? 'Rescan' : 'Scan Resources'}
          </button>
        </div>

        {auditLoaded && auditResources.length === 0 && (
          <p className="text-muted" style={{ padding: '16px 0' }}>No Azure resources found. Make sure you are signed in to Azure and have provisioned resources.</p>
        )}

        {auditResources.length > 0 && (
          <div className="network__audit-grid">
            {auditResources.map(res => {
              const hasIpRules = res.allowed_ips.length > 0
              const hasVnets = res.allowed_vnets.length > 0
              const hasPe = res.private_endpoints.length > 0
              const isSecure = !res.public_access || hasIpRules || hasPe
              return (
                <div key={`${res.resource_group}-${res.name}`} className={`network__audit-card ${isSecure ? 'network__audit-card--secure' : 'network__audit-card--exposed'}`}>
                  <div className="network__audit-card-header">
                    <div className="network__audit-card-title">
                      <div className="network__audit-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d={RESOURCE_AUDIT_ICONS[res.icon] || RESOURCE_AUDIT_ICONS.storage} />
                        </svg>
                      </div>
                      <div>
                        <strong>{res.name}</strong>
                        <span className="network__audit-type">{res.type}</span>
                      </div>
                    </div>
                    <span className={`badge ${res.public_access ? 'badge--err' : 'badge--ok'}`}>
                      {res.public_access ? 'Public' : 'Restricted'}
                    </span>
                  </div>

                  <div className="network__audit-card-body">
                    <div className="network__audit-row">
                      <span className="network__audit-label">Resource Group</span>
                      <span>{res.resource_group}</span>
                    </div>
                    <div className="network__audit-row">
                      <span className="network__audit-label">Default Action</span>
                      <span className={res.default_action === 'Allow' ? 'text-warn' : 'text-ok'}>{res.default_action}</span>
                    </div>
                    {res.https_only !== undefined && (
                      <div className="network__audit-row">
                        <span className="network__audit-label">HTTPS Only</span>
                        <span className={res.https_only ? 'text-ok' : 'text-warn'}>{res.https_only ? 'Yes' : 'No'}</span>
                      </div>
                    )}
                    {res.min_tls_version && (
                      <div className="network__audit-row">
                        <span className="network__audit-label">Min TLS</span>
                        <span className={res.min_tls_version === 'TLS1_2' ? 'text-ok' : 'text-warn'}>{res.min_tls_version}</span>
                      </div>
                    )}

                    {/* Allowed IPs */}
                    {hasIpRules && (
                      <div className="network__audit-section">
                        <span className="network__audit-label">Allowed IPs ({res.allowed_ips.length})</span>
                        <div className="tag-list">
                          {res.allowed_ips.map(ip => <span key={ip} className="tag">{ip}</span>)}
                        </div>
                      </div>
                    )}

                    {/* VNet Rules */}
                    {hasVnets && (
                      <div className="network__audit-section">
                        <span className="network__audit-label">VNet Rules ({res.allowed_vnets.length})</span>
                        <div className="tag-list">
                          {res.allowed_vnets.map(v => <span key={v} className="tag tag--sm">{v.split('/').pop()}</span>)}
                        </div>
                      </div>
                    )}

                    {/* Private Endpoints */}
                    {hasPe && (
                      <div className="network__audit-section">
                        <span className="network__audit-label">Private Endpoints ({res.private_endpoints.length})</span>
                        <div className="tag-list">
                          {res.private_endpoints.map(pe => <span key={pe} className="tag tag--ok">{pe}</span>)}
                        </div>
                      </div>
                    )}

                    {!hasIpRules && !hasVnets && !hasPe && res.public_access && (
                      <div className="network__audit-warning">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                        No IP restrictions, VNets, or private endpoints configured. This resource is accessible from all networks.
                      </div>
                    )}

                    {/* Extra properties */}
                    {Object.entries(res.extra).filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => (
                      <div key={k} className="network__audit-row">
                        <span className="network__audit-label">{k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                        <span className={typeof v === 'boolean' ? (v ? 'text-ok' : 'text-warn') : ''}>
                          {typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Endpoint listing */}
      <div className="network__endpoints">
        <div className="network__endpoints-header">
          <h4>Registered Endpoints</h4>
          <div className="network__endpoints-filters">
            <input
              className="input input--sm"
              placeholder="Filter endpoints..."
              value={filter}
              onChange={e => setFilter(e.target.value)}
            />
            <select
              className="input input--sm"
              value={categoryFilter || ''}
              onChange={e => setCategoryFilter(e.target.value || null)}
            >
              <option value="">All categories</option>
              {CATEGORY_ORDER.map(c => (
                <option key={c} value={c}>{CATEGORY_LABELS[c] || c}</option>
              ))}
            </select>
            <label className="form__check form__check--inline">
              <input type="checkbox" checked={showTunnelOnly} onChange={e => setShowTunnelOnly(e.target.checked)} />
              Tunnel-exposed only
            </label>
          </div>
        </div>

        {allCategories.map(cat => (
          <div key={cat} className="network__ep-group">
            <div className="network__ep-group-label">{CATEGORY_LABELS[cat] || cat}</div>
            <table className="network__ep-table">
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Path</th>
                  <th>Auth</th>
                  <th>Tunnel</th>
                </tr>
              </thead>
              <tbody>
                {grouped[cat].map(ep => {
                  const probed = 'requires_auth' in ep ? ep as ProbedEndpoint : null
                  return (
                    <tr key={`${ep.method}-${ep.path}`}>
                      <td><span className={`network__method network__method--${ep.method.toLowerCase()}`}>{ep.method}</span></td>
                      <td><code>{ep.path}</code></td>
                      <td>
                        {probed?.auth_type === 'admin_key'
                          ? <span className="badge badge--warn badge--sm" title="Protected by admin secret">Admin Key</span>
                          : probed?.auth_type === 'bot_jwt'
                            ? <span className={`badge ${probed.framework_auth_ok ? 'badge--ok' : 'badge--err'} badge--sm`} title={probed.framework_auth_ok ? 'Bot Framework JWT validated (401 on bad token)' : 'Bot Framework JWT NOT enforced -- unauthenticated POST accepted'}>
                                Bot JWT {probed.framework_auth_ok ? '' : '!'}
                              </span>
                            : probed?.auth_type === 'acs_token'
                              ? <span className={`badge ${probed.framework_auth_ok ? 'badge--ok' : 'badge--err'} badge--sm`} title={probed.framework_auth_ok ? 'ACS callback token validated (401 on missing token)' : 'ACS callback token NOT enforced -- unauthenticated POST accepted'}>
                                  ACS Token {probed.framework_auth_ok ? '' : '!'}
                                </span>
                              : probed?.auth_type === 'health'
                                ? <span className="badge badge--muted badge--sm" title="Health/info endpoint, intentionally public">Health</span>
                                : probed?.auth_type === 'open'
                                  ? <span className="badge badge--err badge--sm" title="No authentication detected">Open</span>
                                  : <span className="badge badge--muted badge--sm">{probing ? '...' : '--'}</span>
                        }
                      </td>
                      <td>
                        {probed ? (
                          probed.tunnel_blocked === true
                            ? <span className="badge badge--err badge--sm">Blocked</span>
                            : probed.tunnel_blocked === false
                              ? <span className="badge badge--ok badge--sm">Exposed</span>
                              : <span className="badge badge--muted badge--sm">?</span>
                        ) : ep.tunnel_exposed ? (
                          <span className="badge badge--ok badge--sm">Exposed</span>
                        ) : (
                          <span className="badge badge--muted badge--sm">Local</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ))}

        {allCategories.length === 0 && (
          <p className="text-muted" style={{ padding: 16 }}>No endpoints match the current filter.</p>
        )}
      </div>
    </div>
  )
}
