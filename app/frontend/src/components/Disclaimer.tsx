import { useState, useEffect } from 'react'

const DISCLAIMER_KEY = 'polyclaw_disclaimer_accepted'

export default function Disclaimer({ onAccept }: { onAccept: () => void }) {
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (localStorage.getItem(DISCLAIMER_KEY)) onAccept()
  }, [onAccept])

  const accept = () => {
    localStorage.setItem(DISCLAIMER_KEY, '1')
    onAccept()
  }

  return (
    <div className="disclaimer-overlay">
      <div className="disclaimer-card">
        <div className="disclaimer-card__icon-wrap">
          <svg className="disclaimer-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </div>
        <h2 className="disclaimer-card__title">Technology Demonstrator &mdash; Risk Disclaimer</h2>
        <div className="disclaimer-card__body">
          <p><strong>This software is a technology demonstrator and is not intended for continuous or production use.</strong></p>
          <ul>
            <li><strong>High-autonomy agent.</strong> This system deploys an AI agent with high autonomy and elevated authorization levels. It can execute code, create and delete cloud resources, send messages, access APIs, push code, and make consequential decisions on your behalf &mdash; without further confirmation.</li>
            <li><strong>Sandbox environments only.</strong> Only run against sandbox Azure subscriptions and disposable GitHub accounts.</li>
            <li><strong>Potential for damage.</strong> The agent may take destructive or irreversible actions including deleting resources, sending unintended messages, pushing code, incurring cloud costs, exhausting API quotas, or exposing credentials.</li>
            <li><strong>No warranty.</strong> Provided under the MIT License, &quot;as is&quot;, without warranty of any kind.</li>
          </ul>
        </div>
        <div className="disclaimer-card__footer">
          <label className="disclaimer-card__check">
            <input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} />
            <span>I acknowledge the risks and accept full responsibility</span>
          </label>
          <button className="btn btn--primary disclaimer-card__btn" disabled={!checked} onClick={accept}>
            Accept &amp; Continue
          </button>
        </div>
      </div>
    </div>
  )
}
