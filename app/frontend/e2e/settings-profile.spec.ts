import { test, expect } from '@playwright/test'
import { mockApi, bypassAuth } from './helpers'

test.describe('Settings page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  })

  test('shows five tabs', async ({ page }) => {
    await page.goto('/settings')
    for (const label of ['Config', 'Channels', 'Infrastructure', 'Sandbox', 'Voice']) {
      await expect(page.locator('.tab', { hasText: label })).toBeVisible()
    }
  })

  test('config tab shows model dropdown', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByText('AI Model')).toBeVisible()
    const select = page.locator('select.input').first()
    const options = await select.locator('option').allTextContents()
    expect(options.some(o => o.includes('GPT-4o'))).toBe(true)
    expect(options.some(o => o.includes('GPT-4o Mini'))).toBe(true)
  })

  test('config tab shows system prompt and agent name', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByText('System Prompt')).toBeVisible()
    await expect(page.getByText('Agent Name')).toBeVisible()
  })

  test('save config sends POST', async ({ page }) => {
    let saveCalled = false
    await page.route('**/api/setup/config', route => {
      if (route.request().method() === 'POST') {
        saveCalled = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        COPILOT_MODEL: 'gpt-4o', AGENT_NAME: 'Polyclaw', SYSTEM_PROMPT: 'You are Polyclaw.',
      }) })
    })
    await page.goto('/settings')
    await page.getByRole('button', { name: 'Save Config' }).click()
    expect(saveCalled).toBe(true)
  })

  test('channels tab shows tunnel section', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('.tab', { hasText: 'Channels' }).click()
    await expect(page.locator('.card__section h4', { hasText: 'Tunnel' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start Tunnel' })).toBeVisible()
  })

  test('channels tab shows telegram section', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('.tab', { hasText: 'Channels' }).click()
    await expect(page.getByText('Telegram')).toBeVisible()
    await expect(page.getByPlaceholder('Bot token from @BotFather')).toBeVisible()
  })

  test('infrastructure tab shows deploy/decommission buttons', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('.tab', { hasText: 'Infrastructure' }).click()
    await expect(page.getByRole('button', { name: 'Deploy Infrastructure' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Decommission' })).toBeVisible()
  })

  test('sandbox tab shows config form', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('.tab', { hasText: 'Sandbox' }).click()
    await expect(page.getByText('Enable sandbox mode')).toBeVisible()
    await expect(page.getByText('Sync data to sandbox')).toBeVisible()
    await expect(page.getByText('Session Pool Endpoint')).toBeVisible()
  })

  test('sandbox tab shows whitelist tags', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('.tab', { hasText: 'Sandbox' }).click()
    await expect(page.getByText('requests')).toBeVisible()
    await expect(page.getByText('pandas')).toBeVisible()
  })

  test('voice tab shows configuration status', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('.tab', { hasText: 'Voice' }).click()
    await expect(page.getByText('Voice Call Configuration')).toBeVisible()
    await expect(page.getByText('Not configured')).toBeVisible()
  })
})

test.describe('Profile page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/profile')
    await expect(page.getByRole('heading', { name: 'Agent Profile' })).toBeVisible()
  })

  test('shows agent name and personality', async ({ page }) => {
    await page.goto('/profile')
    await expect(page.getByText('Polyclaw Agent')).toBeVisible()
    await expect(page.getByText('Helpful and proactive assistant')).toBeVisible()
  })

  test('shows instructions', async ({ page }) => {
    await page.goto('/profile')
    await expect(page.getByText('You are a coding assistant.')).toBeVisible()
  })

  test('edit button toggles edit form', async ({ page }) => {
    await page.goto('/profile')
    await page.getByRole('button', { name: 'Edit' }).click()
    await expect(page.locator('.form')).toBeVisible()
    await expect(page.locator('input.input').first()).toHaveValue('Polyclaw Agent')
  })

  test('save button sends PUT', async ({ page }) => {
    let putCalled = false
    await page.route('**/api/profile', route => {
      if (route.request().method() === 'PUT') {
        putCalled = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        name: 'Polyclaw Agent', personality: 'Helpful and proactive assistant',
        instructions: 'You are a coding assistant.', avatar_url: null,
        contributions: [{ date: '2026-02-14', user: 3, scheduled: 1 }],
      }) })
    })
    await page.goto('/profile')
    await page.getByRole('button', { name: 'Edit' }).click()
    await page.getByRole('button', { name: 'Save' }).click()
    expect(putCalled).toBe(true)
  })

  test('shows activity canvas', async ({ page }) => {
    await page.goto('/profile')
    await expect(page.locator('.contributions__canvas')).toBeVisible()
  })
})
