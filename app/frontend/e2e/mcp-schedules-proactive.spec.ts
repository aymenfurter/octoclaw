import { test, expect } from '@playwright/test'
import { mockApi, bypassAuth } from './helpers'

test.describe('MCP Servers page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/mcp')
    await expect(page.getByRole('heading', { name: 'MCP Servers' })).toBeVisible()
  })

  test('shows My Servers and Discover tabs', async ({ page }) => {
    await page.goto('/mcp')
    await expect(page.getByRole('button', { name: 'My Servers' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Discover' })).toBeVisible()
  })

  test('lists configured servers', async ({ page }) => {
    await page.goto('/mcp')
    await expect(page.getByText('filesystem')).toBeVisible()
    await expect(page.getByText('my-http-server')).toBeVisible()
  })

  test('shows server type badges', async ({ page }) => {
    await page.goto('/mcp')
    // Look for type badges within server cards
    await expect(page.locator('.badge', { hasText: 'local' })).toBeVisible()
    await expect(page.locator('.badge', { hasText: 'http' })).toBeVisible()
  })

  test('builtin server shows built-in badge', async ({ page }) => {
    await page.goto('/mcp')
    await expect(page.getByText('built-in')).toBeVisible()
  })

  test('disabled server shows disabled badge', async ({ page }) => {
    await page.goto('/mcp')
    await expect(page.getByText('disabled')).toBeVisible()
  })

  test('Add Server button opens modal', async ({ page }) => {
    await page.goto('/mcp')
    await page.getByRole('button', { name: 'Add Server' }).click()
    await expect(page.locator('.modal')).toBeVisible()
    await expect(page.getByText('Add MCP Server')).toBeVisible()
  })

  test('add modal has name, type, and description fields', async ({ page }) => {
    await page.goto('/mcp')
    await page.getByRole('button', { name: 'Add Server' }).click()
    await expect(page.locator('.modal').getByText('Name')).toBeVisible()
    await expect(page.locator('.modal').getByText('Type')).toBeVisible()
    await expect(page.locator('.modal').getByText('Description')).toBeVisible()
  })

  test('local type shows command and args fields', async ({ page }) => {
    await page.goto('/mcp')
    await page.getByRole('button', { name: 'Add Server' }).click()
    await expect(page.locator('.modal').getByText('Command')).toBeVisible()
    await expect(page.locator('.modal').getByText('Arguments (one per line)')).toBeVisible()
  })

  test('switching to HTTP type shows URL field', async ({ page }) => {
    await page.goto('/mcp')
    await page.getByRole('button', { name: 'Add Server' }).click()
    await page.locator('.modal select.input').selectOption('http')
    await expect(page.locator('.modal').getByText('URL')).toBeVisible()
    await expect(page.locator('.modal').getByText('Command')).not.toBeVisible()
  })

  test('saving new server sends POST', async ({ page }) => {
    let postCalled = false
    await page.route('**/api/mcp/servers', route => {
      if (route.request().method() === 'POST') {
        postCalled = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      }
      return route.continue()
    })
    await page.goto('/mcp')
    await page.getByRole('button', { name: 'Add Server' }).click()
    await page.locator('.modal input.input').first().fill('test-server')
    await page.locator('.modal').getByRole('button', { name: 'Save' }).click()
    expect(postCalled).toBe(true)
  })

  test('Discover tab shows registry entries', async ({ page }) => {
    await page.goto('/mcp')
    await page.getByRole('button', { name: 'Discover' }).click()
    await expect(page.getByText('GitHub MCP')).toBeVisible()
  })

  test('Discover tab has search input', async ({ page }) => {
    await page.goto('/mcp')
    await page.getByRole('button', { name: 'Discover' }).click()
    await expect(page.getByPlaceholder('Search MCP servers...')).toBeVisible()
  })

  test('Discover tab has pagination', async ({ page }) => {
    await page.goto('/mcp')
    await page.getByRole('button', { name: 'Discover' }).click()
    await expect(page.getByText('Page 1')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Next' })).toBeVisible()
  })

  test('empty state when no servers', async ({ page }) => {
    await page.route('**/api/mcp/servers', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ servers: [] }) }),
    )
    await page.goto('/mcp')
    await expect(page.getByText('No MCP servers configured')).toBeVisible()
  })
})

test.describe('Schedules page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/schedules')
    await expect(page.getByRole('heading', { name: 'Schedules' })).toBeVisible()
  })

  test('lists configured schedules', async ({ page }) => {
    await page.goto('/schedules')
    await expect(page.getByText('Morning Report', { exact: true })).toBeVisible()
    await expect(page.getByText('Weekly Digest', { exact: true })).toBeVisible()
  })

  test('shows cron expressions', async ({ page }) => {
    await page.goto('/schedules')
    await expect(page.getByText('0 9 * * *')).toBeVisible()
    await expect(page.getByText('0 18 * * 5')).toBeVisible()
  })

  test('shows schedule prompts', async ({ page }) => {
    await page.goto('/schedules')
    await expect(page.getByText('Generate a morning report')).toBeVisible()
  })

  test('New Schedule button opens modal', async ({ page }) => {
    await page.goto('/schedules')
    await page.getByRole('button', { name: 'New Schedule' }).click()
    await expect(page.locator('.modal')).toBeVisible()
    await expect(page.getByText('New Schedule').last()).toBeVisible()
  })

  test('schedule modal has correct fields', async ({ page }) => {
    await page.goto('/schedules')
    await page.getByRole('button', { name: 'New Schedule' }).click()
    await expect(page.locator('.modal').getByText('Name')).toBeVisible()
    await expect(page.locator('.modal').getByText('Cron Schedule')).toBeVisible()
    await expect(page.locator('.modal').getByText('Prompt')).toBeVisible()
  })

  test('saving schedule sends POST', async ({ page }) => {
    let postCalled = false
    await page.route('**/api/schedules', route => {
      if (route.request().method() === 'POST') {
        postCalled = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      }
      return route.continue()
    })
    await page.goto('/schedules')
    await page.getByRole('button', { name: 'New Schedule' }).click()
    const modal = page.locator('.modal')
    await modal.locator('input.input').first().fill('Test Schedule')
    await modal.getByRole('button', { name: 'Save' }).click()
    expect(postCalled).toBe(true)
  })

  test('enable/disable toggle calls API', async ({ page }) => {
    let putCalled = false
    await page.route(/\/api\/schedules\/sched-002$/, route => {
      if (route.request().method() === 'PUT') {
        putCalled = true
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
    })
    await page.goto('/schedules')
    // Weekly Digest is disabled — click Enable
    const item = page.locator('.list-item', { hasText: 'Weekly Digest' })
    await item.getByRole('button', { name: 'Enable' }).click()
    expect(putCalled).toBe(true)
  })

  test('empty state when no schedules', async ({ page }) => {
    await page.route('**/api/schedules', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ schedules: [] }) }),
    )
    await page.goto('/schedules')
    await expect(page.getByText('No schedules configured')).toBeVisible()
  })
})

test.describe('Proactive page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/proactive')
    await expect(page.getByRole('heading', { name: 'Proactive' })).toBeVisible()
  })

  test('shows stats', async ({ page }) => {
    await page.goto('/proactive')
    await expect(page.locator('.stats-bar')).toBeVisible()
    await expect(page.getByText('Sent Today')).toBeVisible()
    await expect(page.getByText('Last Sent')).toBeVisible()
  })

  test('shows pending follow-up when present', async ({ page }) => {
    await page.goto('/proactive')
    await expect(page.getByText('You have a PR review waiting')).toBeVisible()
  })

  test('shows history entries', async ({ page }) => {
    await page.goto('/proactive')
    await expect(page.getByText('Reminder: team standup')).toBeVisible()
  })
})
