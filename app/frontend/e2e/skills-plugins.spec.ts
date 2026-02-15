import { test, expect } from '@playwright/test'
import { mockApi, bypassAuth } from './helpers'

test.describe('Skills page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/skills')
    await expect(page.getByRole('heading', { name: 'Skills' })).toBeVisible()
  })

  test('shows installed and marketplace tabs', async ({ page }) => {
    await page.goto('/skills')
    await expect(page.getByRole('button', { name: /Installed/ })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Marketplace' })).toBeVisible()
  })

  test('installed tab shows installed skills with verb badges', async ({ page }) => {
    await page.goto('/skills')
    await expect(page.getByText('/search')).toBeVisible()
    await expect(page.getByText('/summarize')).toBeVisible()
    await expect(page.getByText('web-search')).toBeVisible()
  })

  test('remove button appears on non-builtin skills', async ({ page }) => {
    await page.goto('/skills')
    // web-search is not builtin
    await expect(page.getByRole('button', { name: 'Remove' })).toBeVisible()
  })

  test('marketplace tab shows available skills', async ({ page }) => {
    await page.goto('/skills')
    await page.getByRole('button', { name: 'Marketplace' }).click()
    await expect(page.getByText('daily-briefing')).toBeVisible()
    await expect(page.getByText('note-taking')).toBeVisible()
  })

  test('marketplace shows GET button for not-installed skills', async ({ page }) => {
    await page.goto('/skills')
    await page.getByRole('button', { name: 'Marketplace' }).click()
    const getBtns = page.getByRole('button', { name: 'GET', exact: true })
    await expect(getBtns.first()).toBeVisible()
  })

  test('marketplace shows Installed badge for already installed skills', async ({ page }) => {
    await page.goto('/skills')
    await page.getByRole('button', { name: 'Marketplace' }).click()
    await expect(page.getByText('Installed').first()).toBeVisible()
  })

  test('install button sends POST request', async ({ page }) => {
    let installCalled = false
    await page.route('**/api/skills**', route => {
      const url = route.request().url()
      if (url.includes('/skills/install')) {
        installCalled = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      }
      if (url.includes('/skills/marketplace')) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
          recommended: [
            { name: 'daily-briefing', verb: 'briefing', description: 'Daily briefing', source: 'GitHub Awesome Copilot', category: 'github-awesome', installed: false, recommended: true, edit_count: 8, usage_count: 0 },
          ],
          popular: [], loved: [], github_awesome: [], anthropic: [],
          installed: [],
          all: [
            { name: 'web-search', verb: 'search', description: 'Search the web', source: 'GitHub Awesome Copilot', category: 'github-awesome', installed: true, recommended: true, edit_count: 12, usage_count: 5 },
            { name: 'daily-briefing', verb: 'briefing', description: 'Daily briefing', source: 'GitHub Awesome Copilot', category: 'github-awesome', installed: false, recommended: true, edit_count: 8, usage_count: 0 },
          ],
        }) })
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        skills: [{ name: 'web-search', verb: 'search', description: 'Search the web', installed: true, builtin: false, source: 'marketplace' }],
      }) })
    })
    await page.goto('/skills')
    await page.getByRole('button', { name: 'Marketplace' }).click()
    await expect(page.getByText('daily-briefing')).toBeVisible()
    const getBtns = page.getByRole('button', { name: 'GET', exact: true })
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/skills/install')),
      getBtns.first().click(),
    ])
    expect(installCalled).toBe(true)
  })
})

test.describe('Plugins page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/plugins')
    await expect(page.getByRole('heading', { name: 'Plugins' })).toBeVisible()
  })

  test('displays plugin cards', async ({ page }) => {
    await page.goto('/plugins')
    await expect(page.getByText('GitHub Status')).toBeVisible()
    await expect(page.getByText('Wikipedia Lookup')).toBeVisible()
  })

  test('shows plugin descriptions', async ({ page }) => {
    await page.goto('/plugins')
    await expect(page.getByText('Monitor GitHub service status')).toBeVisible()
    await expect(page.getByText('Search Wikipedia articles')).toBeVisible()
  })

  test('enabled plugin shows Disable button', async ({ page }) => {
    await page.goto('/plugins')
    const ghCard = page.locator('.plugin-card', { hasText: 'GitHub Status' })
    await expect(ghCard.getByRole('button', { name: 'Disable' })).toBeVisible()
  })

  test('disabled plugin shows Enable button', async ({ page }) => {
    await page.goto('/plugins')
    const wikiCard = page.locator('.plugin-card', { hasText: 'Wikipedia Lookup' })
    await expect(wikiCard.getByRole('button', { name: 'Enable' })).toBeVisible()
  })

  test('details button opens modal', async ({ page }) => {
    await page.goto('/plugins')
    const card = page.locator('.plugin-card', { hasText: 'GitHub Status' })
    await card.getByRole('button', { name: 'Details' }).click()
    await expect(page.locator('.modal')).toBeVisible()
    await expect(page.locator('.modal').getByText('GitHub Status')).toBeVisible()
  })

  test('modal shows plugin details', async ({ page }) => {
    await page.goto('/plugins')
    await page.locator('.plugin-card', { hasText: 'GitHub Status' }).getByRole('button', { name: 'Details' }).click()
    await expect(page.locator('.modal')).toBeVisible()
    await expect(page.locator('.modal').getByText('1.0.0')).toBeVisible()
    await expect(page.locator('.modal').getByText('builtin')).toBeVisible()
  })

  test('modal closes on backdrop click', async ({ page }) => {
    await page.goto('/plugins')
    page.locator('.plugin-card', { hasText: 'GitHub Status' }).getByRole('button', { name: 'Details' }).click()
    await expect(page.locator('.modal')).toBeVisible()
    await page.locator('.modal-overlay').click({ position: { x: 5, y: 5 } })
    await expect(page.locator('.modal')).not.toBeVisible()
  })

  test('toggle plugin sends correct API call', async ({ page }) => {
    let disableCalled = false
    await page.route(/\/api\/plugins\/github-status\/disable/, route => {
      disableCalled = true
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
    })
    await page.goto('/plugins')
    const ghCard = page.locator('.plugin-card', { hasText: 'GitHub Status' })
    await ghCard.getByRole('button', { name: 'Disable' }).click()
    expect(disableCalled).toBe(true)
  })

  test('shows empty state when no plugins', async ({ page }) => {
    await page.route('**/api/plugins', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ plugins: [] }) }),
    )
    await page.goto('/plugins')
    await expect(page.getByText('No plugins found')).toBeVisible()
  })
})
