/* -----------------------------------------------------------------------
   API client for polyclaw backend.  All HTTP calls go through `api()`.
   WebSocket chat is managed separately via `createChatSocket()`.
   ----------------------------------------------------------------------- */

import type { ApiResponse } from './types'

// ---------------------------------------------------------------------------
// Auth token management
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'polyclaw_secret'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/** Extract ?secret= from URL on first load. */
export function extractTokenFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search)
  const secret = params.get('secret')
  if (secret) {
    setToken(secret)
    // Clean URL without reloading
    const url = new URL(window.location.href)
    url.searchParams.delete('secret')
    window.history.replaceState({}, '', url.toString())
  }
  return secret
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

function authHeaders(): Record<string, string> {
  const token = getToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

export async function api<T = ApiResponse>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const url = path.startsWith('/') ? path : `/api/${path}`
  const res = await fetch(url, {
    ...opts,
    headers: { ...authHeaders(), ...(opts.headers as Record<string, string> || {}) },
  })
  if (res.status === 401) {
    clearToken()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.text()
    throw new Error(body || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function apiFormData<T = ApiResponse>(
  path: string,
  formData: FormData,
): Promise<T> {
  const url = path.startsWith('/') ? path : `/api/${path}`
  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { method: 'POST', headers, body: formData })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Auth check
// ---------------------------------------------------------------------------

export async function checkAuth(): Promise<boolean> {
  try {
    const res = await api<{ authenticated: boolean }>('auth/check', { method: 'POST' })
    return res.authenticated
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// WebSocket chat
// ---------------------------------------------------------------------------

export interface ChatSocket {
  send: (action: string, payload?: Record<string, unknown>) => void
  close: () => void
  onMessage: (handler: (data: unknown) => void) => void
  onOpen: (handler: () => void) => void
  onClose: (handler: () => void) => void
}

export function createChatSocket(): ChatSocket {
  // In mock mode, provide a fake socket that is always "connected"
  const isMock = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_MOCK === '1'
  if (isMock) {
    let openHandler: (() => void) | null = null
    let messageHandler: ((data: unknown) => void) | null = null

    // Fire open on next tick so handlers can be registered first
    setTimeout(() => openHandler?.(), 0)

    return {
      send(_action, _payload = {}) {
        // Simulate an echo reply after a short delay
        setTimeout(() => {
          messageHandler?.({ type: 'delta', content: 'Mock mode — no backend connected. Use the reasoning demo panel to test the ticker.' })
          setTimeout(() => messageHandler?.({ type: 'done' }), 100)
        }, 300)
      },
      close() {},
      onMessage(handler) { messageHandler = handler },
      onOpen(handler) { openHandler = handler; },
      onClose() {},
    }
  }

  const token = getToken()
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${proto}//${window.location.host}/api/chat/ws${token ? `?token=${token}` : ''}`

  let ws: WebSocket | null = null
  let messageHandler: ((data: unknown) => void) | null = null
  let openHandler: (() => void) | null = null
  let closeHandler: (() => void) | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    ws = new WebSocket(wsUrl)
    ws.onopen = () => openHandler?.()
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        messageHandler?.(data)
      } catch { /* ignore */ }
    }
    ws.onclose = () => {
      closeHandler?.()
      reconnectTimer = setTimeout(connect, 3000)
    }
    ws.onerror = () => {}
  }

  connect()

  return {
    send(action, payload = {}) {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action, ...payload }))
      }
    },
    close() {
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close()
    },
    onMessage(handler) { messageHandler = handler },
    onOpen(handler) { openHandler = handler },
    onClose(handler) { closeHandler = handler },
  }
}
