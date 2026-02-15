import { useState, useEffect, useCallback } from 'react'

interface ToastItem {
  id: number
  message: string
  type: 'success' | 'error' | 'info'
}

let toastId = 0
let globalAddToast: ((msg: string, type: ToastItem['type']) => void) | null = null

/** Call from anywhere to show a toast. */
export function showToast(message: string, type: ToastItem['type'] = 'info') {
  globalAddToast?.(message, type)
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const add = useCallback((message: string, type: ToastItem['type']) => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }, [])

  useEffect(() => {
    globalAddToast = add
    return () => { globalAddToast = null }
  }, [add])

  if (!toasts.length) return null

  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast--${t.type}`}>
          {t.message}
        </div>
      ))}
    </div>
  )
}
