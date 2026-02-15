/**
 * Dev-only panel for testing the reasoning ticker with different scenarios and visual modes.
 * Only rendered when VITE_MOCK=1.
 */
import { useCallback, useRef } from 'react'

// ── Thought scenarios ──────────────────────────────────────────────────

const SCENARIOS: { label: string; description: string; text: string; delay?: number }[] = [
  {
    label: 'Short burst',
    description: 'Quick 12-word thought',
    text: 'The user wants a summary. I should fetch the URL first and parse the HTML content.',
  },
  {
    label: 'Long reasoning',
    description: '80+ words, multi-sentence',
    text:
      'Let me think about this step by step. The user is asking about deployment strategies for containerized applications. ' +
      'First, I need to consider the current infrastructure setup — they mentioned Azure Container Apps. ' +
      'I should check if they have an existing resource group or if we need to provision one. ' +
      'The Dockerfile looks standard, but the entrypoint script might need adjustments for the new environment variables. ' +
      'I also need to verify that the Key Vault references are correctly configured and that the managed identity has the right permissions. ' +
      'Finally, I should recommend a blue-green deployment pattern to minimize downtime during the rollout.',
  },
  {
    label: 'Code analysis',
    description: 'Technical with long tokens',
    text:
      'Analyzing the useLayoutEffect hook implementation. The offsetLeft measurement occurs synchronously before paint. ' +
      'The translateX transform shifts the container. Each WindowWord carries an idx and distance property. ' +
      'Performance consideration: will-change enables GPU compositing layer promotion for smoother animation.',
  },
  {
    label: 'Rapid-fire',
    description: 'Very short words, fast pace',
    text:
      'Go get it. Run it. Try the fix. Is it ok? Yes. No. Wait. Stop. Let me see. Got it. ' +
      'Do it now. Set it up. Read the docs. Find the bug. Ship the code.',
    delay: 80,
  },
  {
    label: 'Deep thought',
    description: 'Slow, philosophical',
    text:
      'This is an interesting architectural decision that requires careful consideration. ' +
      'The tradeoff between consistency and availability in distributed systems is fundamentally about latency tolerance. ' +
      'Perhaps a hybrid approach would serve us best here.',
    delay: 200,
  },
]

interface Props {
  feedReasoning: (text: string) => void
  clearReasoning: () => void
  tickerMode: string
  setTickerMode: (mode: string) => void
  modes: { id: string; label: string }[]
}

export default function MockReasoningPanel({ feedReasoning, clearReasoning, tickerMode, setTickerMode, modes }: Props) {
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stop = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    clearReasoning()
  }, [clearReasoning])

  const run = useCallback((scenario: typeof SCENARIOS[number]) => {
    stop()
    const words = scenario.text.split(/\s+/)
    let i = 0
    const chunkSize = 3

    timerRef.current = setInterval(() => {
      if (i >= words.length) {
        if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
        setTimeout(() => clearReasoning(), 2000)
        return
      }
      const chunk = words.slice(i, i + chunkSize).join(' ')
      feedReasoning(chunk)
      i += chunkSize
    }, scenario.delay ?? 140)
  }, [feedReasoning, clearReasoning, stop])

  return (
    <div className="mock-panel">
      <div className="mock-panel__header">
        <span className="mock-panel__title">Reasoning Ticker Lab</span>
        <button className="mock-panel__stop" onClick={stop}>Stop</button>
      </div>

      {/* Mode selector */}
      <div className="mock-panel__section">
        <span className="mock-panel__label">Visual Mode</span>
        <div className="mock-panel__modes">
          {modes.map((m, i) => (
            <button
              key={m.id}
              className={`mock-panel__mode ${tickerMode === m.id ? 'mock-panel__mode--active' : ''}`}
              onClick={() => setTickerMode(m.id)}
              title={m.label}
            >
              <span className="mock-panel__mode-num">{i + 1}</span>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Scenario buttons */}
      <div className="mock-panel__section">
        <span className="mock-panel__label">Test Scenarios</span>
        <div className="mock-panel__grid">
          {SCENARIOS.map((s) => (
            <button
              key={s.label}
              className="mock-panel__btn"
              onClick={() => run(s)}
              title={s.description}
            >
              <span className="mock-panel__btn-label">{s.label}</span>
              <span className="mock-panel__btn-desc">{s.description}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
