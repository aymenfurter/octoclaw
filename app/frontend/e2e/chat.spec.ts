import { test, expect } from '@playwright/test'
import { mockApi, bypassAuth } from './helpers'

test.describe('Chat page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders empty state with hero message', async ({ page }) => {
    await page.goto('/chat')
    await expect(page.getByText('What can I help you with?')).toBeVisible()
  })

  test('chat input is visible', async ({ page }) => {
    await page.goto('/chat')
    await expect(page.locator('.chat-input')).toBeVisible()
  })

  test('new session button is visible in toolbar', async ({ page }) => {
    await page.goto('/chat')
    await expect(page.locator('.chat-toolbar').getByTitle('New session')).toBeVisible()
  })

  test('sessions sidebar toggle works', async ({ page }) => {
    await page.goto('/chat')
    const toggleBtn = page.locator('.chat-toolbar').getByTitle('Sessions')
    await toggleBtn.click()
    await expect(page.locator('.chat-sidebar')).toHaveClass(/chat-sidebar--open/)
    await expect(page.getByText('Hello, World!')).toBeVisible()
    await expect(page.getByText('Deploy the app')).toBeVisible()
  })

  test('slash command autocomplete appears when typing /', async ({ page }) => {
    await page.goto('/chat')
    // Force-enable the input since WebSocket is aborted in tests
    await page.waitForSelector('.chat-input')
    await page.evaluate(() => {
      const input = document.querySelector('.chat-input') as HTMLTextAreaElement
      if (input) {
        input.disabled = false
        input.dispatchEvent(new Event('change'))
      }
    })
    await page.locator('.chat-input').fill('/')
    // Autocomplete should show commands
    await expect(page.locator('.chat-autocomplete')).toBeVisible({ timeout: 3000 })
    await expect(page.locator('.chat-autocomplete__cmd').first()).toBeVisible()
  })

  test('slash command list contains expected commands', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForSelector('.chat-input')
    await page.evaluate(() => {
      const input = document.querySelector('.chat-input') as HTMLTextAreaElement
      if (input) {
        input.disabled = false
        input.dispatchEvent(new Event('change'))
      }
    })
    await page.locator('.chat-input').fill('/m')
    await expect(page.locator('.chat-autocomplete')).toBeVisible({ timeout: 3000 })
    // Should show /model, /models, /mcp
    const items = page.locator('.chat-autocomplete__cmd')
    const texts = await items.allTextContents()
    expect(texts.some(t => t.includes('/model'))).toBe(true)
  })

  test('skill dropdown is visible when skills are loaded', async ({ page }) => {
    await page.goto('/chat')
    // Skills are loaded from /api/skills in useChat
    await expect(page.locator('.chat-skill-select')).toBeVisible()
    await expect(page.locator('.chat-skill-select option')).toHaveCount(3) // "Chat" + 2 skills
  })

  test('skill dropdown has correct options', async ({ page }) => {
    await page.goto('/chat')
    await expect(page.locator('.chat-skill-select')).toBeVisible()
    await expect(page.locator('.chat-skill-select option').first()).toHaveText('Chat')
    const options = page.locator('.chat-skill-select option')
    const count = await options.count()
    expect(count).toBe(3)
    const texts = await options.allTextContents()
    expect(texts.some(t => t.includes('search'))).toBe(true)
    expect(texts.some(t => t.includes('summarize'))).toBe(true)
  })

  test('send button is disabled when input is empty', async ({ page }) => {
    await page.goto('/chat')
    await expect(page.locator('.chat-send-btn')).toBeDisabled()
  })
})
