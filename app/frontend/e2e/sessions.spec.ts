import { test, expect } from '@playwright/test'
import { mockApi, bypassAuth } from './helpers'

test.describe('Sessions page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/sessions')
    await expect(page.getByRole('heading', { name: 'Sessions' })).toBeVisible()
  })

  test('displays stats bar with correct values', async ({ page }) => {
    await page.goto('/sessions')
    await expect(page.locator('.stats-bar')).toBeVisible()
    await expect(page.getByText('Total')).toBeVisible()
    await expect(page.getByText('Today')).toBeVisible()
    await expect(page.getByText('This Week')).toBeVisible()
    await expect(page.getByText('Avg Messages')).toBeVisible()
  })

  test('lists sessions', async ({ page }) => {
    await page.goto('/sessions')
    await expect(page.getByText('Hello, World!')).toBeVisible()
    await expect(page.getByText('Deploy the app')).toBeVisible()
  })

  test('shows session model badges', async ({ page }) => {
    await page.goto('/sessions')
    await expect(page.locator('.sessions-item__model', { hasText: 'gpt-4o' }).first()).toBeVisible()
    await expect(page.locator('.sessions-item__model', { hasText: 'gpt-4o-mini' })).toBeVisible()
  })

  test('clicking a session loads detail panel', async ({ page }) => {
    await page.goto('/sessions')
    await page.getByText('Hello, World!').click()
    await expect(page.locator('.sessions-detail')).toBeVisible()
    await expect(page.getByText('Hi! How can I help?')).toBeVisible()
  })

  test('delete button appears in detail panel', async ({ page }) => {
    await page.goto('/sessions')
    await page.getByText('Hello, World!').click()
    await expect(page.getByRole('button', { name: 'Delete' })).toBeVisible()
  })

  test('refresh button reloads data', async ({ page }) => {
    let fetchCount = 0
    await page.route('**/api/sessions**', route => {
      const url = route.request().url()
      if (url.includes('/stats')) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 0, today: 0, this_week: 0, avg_messages: 0 }) })
      }
      fetchCount++
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    })
    await page.goto('/sessions')
    await page.getByRole('button', { name: 'Refresh' }).click()
    expect(fetchCount).toBeGreaterThanOrEqual(2)
  })

  test('shows empty state when no sessions', async ({ page }) => {
    await page.route('**/api/sessions**', route => {
      const url = route.request().url()
      if (url.includes('/stats')) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 0, today: 0, this_week: 0, avg_messages: 0 }) })
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    })
    await page.goto('/sessions')
    await expect(page.getByText('No sessions yet')).toBeVisible()
  })
})
