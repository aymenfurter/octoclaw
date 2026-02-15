import { useEffect, useRef } from 'react'
import * as AdaptiveCards from 'adaptivecards'

/**
 * Props match the attachment shape sent by the backend:
 *   { contentType: "application/vnd.microsoft.card.adaptive", content: { ... } }
 *
 * We also accept the inner card directly (when `content` has `type: "AdaptiveCard"`).
 */
interface Props {
  /** The card payload – either the full attachment or just the inner card JSON. */
  card: Record<string, unknown>
}

/**
 * Renders a Microsoft Adaptive Card using the official SDK.
 */
export default function AdaptiveCardRenderer({ card }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    // Determine the actual card JSON.
    // The backend sends attachments as { contentType, content }.
    // If we receive that wrapper, unwrap it.
    let cardPayload: Record<string, unknown>
    if (card.contentType && card.content && typeof card.content === 'object') {
      cardPayload = card.content as Record<string, unknown>
    } else {
      cardPayload = card
    }

    const adaptiveCard = new AdaptiveCards.AdaptiveCard()

    // Configure host – dark-theme friendly defaults.
    adaptiveCard.hostConfig = new AdaptiveCards.HostConfig({
      fontFamily: 'inherit',
      containerStyles: {
        default: {
          backgroundColor: '#00000000',
          foregroundColors: {
            default: { default: '#e0e0e0', subtle: '#a0a0a0' },
            accent: { default: '#58a6ff', subtle: '#388bfd' },
            attention: { default: '#f85149', subtle: '#da3633' },
            good: { default: '#3fb950', subtle: '#2ea043' },
            warning: { default: '#d29922', subtle: '#bb8009' },
            light: { default: '#c9d1d9', subtle: '#8b949e' },
            dark: { default: '#0d1117', subtle: '#161b22' },
          },
        },
        emphasis: {
          backgroundColor: '#161b2266',
          foregroundColors: {
            default: { default: '#e0e0e0', subtle: '#a0a0a0' },
            accent: { default: '#58a6ff', subtle: '#388bfd' },
            attention: { default: '#f85149', subtle: '#da3633' },
            good: { default: '#3fb950', subtle: '#2ea043' },
            warning: { default: '#d29922', subtle: '#bb8009' },
            light: { default: '#c9d1d9', subtle: '#8b949e' },
            dark: { default: '#0d1117', subtle: '#161b22' },
          },
        },
      },
      actions: {
        actionAlignment: 'stretch' as unknown as AdaptiveCards.ActionAlignment,
        actionsOrientation: 'horizontal' as unknown as AdaptiveCards.Orientation,
        buttonSpacing: 8,
        maxActions: 10,
        showCard: { actionMode: 'inline' as unknown as AdaptiveCards.ShowCardActionMode },
      },
      spacing: {
        small: 4,
        default: 8,
        medium: 12,
        large: 16,
        extraLarge: 24,
        padding: 12,
      },
      imageSizes: {
        small: 32,
        medium: 48,
        large: 64,
      },
      factSet: {
        title: { weight: 600 as unknown as AdaptiveCards.TextWeight, color: 'default' as unknown as AdaptiveCards.TextColor, size: 'default' as unknown as AdaptiveCards.TextSize, wrap: true },
        value: { weight: 400 as unknown as AdaptiveCards.TextWeight, color: 'default' as unknown as AdaptiveCards.TextColor, size: 'default' as unknown as AdaptiveCards.TextSize, wrap: true },
        spacing: 8,
      },
    })

    // Handle Action.OpenUrl – open in a new tab.
    adaptiveCard.onExecuteAction = (action: AdaptiveCards.Action) => {
      if (action instanceof AdaptiveCards.OpenUrlAction && action.url) {
        window.open(action.url, '_blank', 'noopener')
      }
    }

    try {
      adaptiveCard.parse(cardPayload)
      const rendered = adaptiveCard.render()
      if (rendered) {
        containerRef.current.innerHTML = ''
        containerRef.current.appendChild(rendered)
      }
    } catch {
      // Fallback: show raw JSON
      containerRef.current.innerHTML = `<pre style="white-space:pre-wrap;font-size:0.85em">${JSON.stringify(cardPayload, null, 2)}</pre>`
    }
  }, [card])

  return <div ref={containerRef} className="adaptive-card" />
}
