import { useState } from 'react'

interface Props {
  onLogin: (secret: string) => void
}

export default function LoginOverlay({ onLogin }: Props) {
  const [secret, setSecret] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (secret.trim()) onLogin(secret.trim())
  }

  return (
    <div className="login-overlay">
      <div className="login-card">
        <img src="/logo.png" alt="octoclaw" className="login-card__logo" />
        <p className="login-card__subtitle">Enter your admin secret to continue</p>
        <form onSubmit={handleSubmit} className="login-card__form">
          <input
            type="password"
            value={secret}
            onChange={e => setSecret(e.target.value)}
            placeholder="Admin secret"
            className="input"
            autoFocus
          />
          <button type="submit" className="btn btn--primary" disabled={!secret.trim()}>
            Sign In
          </button>
        </form>
      </div>
    </div>
  )
}
