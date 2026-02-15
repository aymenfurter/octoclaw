import { useNavigate } from 'react-router-dom'
import { IconZap, IconPackage, IconServer, IconCalendar } from '../components/Icons'

const ITEMS = [
  { path: '/skills', label: 'Skills', desc: 'Manage installed skills and browse the marketplace', Icon: IconZap },
  { path: '/plugins', label: 'Plugins', desc: 'Enable, disable and import agent plugins', Icon: IconPackage },
  { path: '/mcp', label: 'MCP Servers', desc: 'Configure Model Context Protocol servers', Icon: IconServer },
  { path: '/schedules', label: 'Schedules', desc: 'Set up recurring automated tasks', Icon: IconCalendar },
] as const

export default function Customization() {
  const navigate = useNavigate()

  return (
    <div className="page">
      <div className="page__header">
        <h1>Customization</h1>
      </div>

      <div className="grid">
        {ITEMS.map(({ path, label, desc, Icon }) => (
          <button
            key={path}
            className="card"
            style={{ cursor: 'pointer', textAlign: 'left' }}
            onClick={() => navigate(path)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <Icon width={20} height={20} style={{ color: 'var(--gold)' }} />
              <span style={{ fontWeight: 600, fontSize: 15 }}>{label}</span>
            </div>
            <p className="text-muted" style={{ fontSize: 13, lineHeight: 1.5 }}>{desc}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
