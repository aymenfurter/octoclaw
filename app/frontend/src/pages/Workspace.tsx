import { useState, useEffect } from 'react'
import { api } from '../api'
import { IconFolder, IconFile } from '../components/Icons'
import type { WorkspaceEntry } from '../types'

export function WorkspaceContent() {
  const [path, setPath] = useState('data')
  const [entries, setEntries] = useState<WorkspaceEntry[]>([])
  const [preview, setPreview] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async (p: string) => {
    setPath(p)
    setPreview(null)
    setLoading(true)
    try {
      const r = await api<{ status: string; entries: WorkspaceEntry[] }>(`workspace/list?path=${encodeURIComponent(p)}`)
      setEntries(r.entries || [])
    } catch { setEntries([]) }
    setLoading(false)
  }

  useEffect(() => { load('data') }, [])

  const readFile = async (filePath: string) => {
    try {
      const r = await api<{ status: string; content?: string; binary?: boolean; size?: number }>(`workspace/read?path=${encodeURIComponent(filePath)}`)
      if (r.binary) {
        setPreview(`(binary file, ${formatSize(r.size || 0)})`)
      } else {
        setPreview(r.content || '')
      }
    } catch (e: any) { setPreview(`Error: ${e.message}`) }
  }

  const parts = path.split('/')

  return (
    <>
      <div className="page__header">
        <h1>Workspace</h1>
      </div>

      {/* Breadcrumb */}
      <div className="breadcrumb">
        {parts.map((part, i) => {
          const crumbPath = parts.slice(0, i + 1).join('/')
          const isLast = i === parts.length - 1
          return (
            <span key={i}>
              {isLast ? (
                <span className="breadcrumb__current">{part}</span>
              ) : (
                <button className="breadcrumb__link" onClick={() => load(crumbPath)}>{part}</button>
              )}
              {!isLast && <span className="breadcrumb__sep">/</span>}
            </span>
          )
        })}
      </div>

      <div className="workspace-layout">
        <div className="workspace-files">
          {loading && <div className="spinner" />}

          {/* Parent directory */}
          {parts.length > 1 && (
            <button className="workspace-entry workspace-entry--dir" onClick={() => load(parts.slice(0, -1).join('/'))}>
              <span className="workspace-entry__icon"><IconFolder width={16} height={16} /></span>
              <span>..</span>
            </button>
          )}

          {entries.map(entry => (
            <button
              key={entry.name}
              className={`workspace-entry ${entry.is_dir ? 'workspace-entry--dir' : ''}`}
              onClick={() => entry.is_dir ? load(entry.path) : readFile(entry.path)}
            >
              <span className="workspace-entry__icon">{entry.is_dir ? <IconFolder width={16} height={16} /> : <IconFile width={16} height={16} />}</span>
              <span className="workspace-entry__name">{entry.name}</span>
              {!entry.is_dir && entry.size != null && (
                <span className="workspace-entry__size text-muted">{formatSize(entry.size)}</span>
              )}
            </button>
          ))}

          {!loading && entries.length === 0 && <p className="text-muted">Empty directory</p>}
        </div>

        {preview !== null && (
          <div className="workspace-preview card">
            <pre>{preview}</pre>
          </div>
        )}
      </div>
    </>
  )
}

export default function Workspace() {
  return <div className="page"><WorkspaceContent /></div>
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
