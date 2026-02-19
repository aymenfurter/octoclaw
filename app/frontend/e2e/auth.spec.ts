import { test, expect } from '@playwright/test'
import { mockApi } from './helpers'

test.describe('Disclaimer gate', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
  })

  test('shows disclaimer on first visit', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.disclaimer-card')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Technology Demonstrator' })).toBeVisible()
  })

  test('accept button is disabled until checkbox is checked', async ({ page }) => {
    await page.goto('/')
    const btn = page.locator('.disclaimer-card .btn--primary')
    await expect(btn).toBeDisabled()

    await page.locator('.disclaimer-card input[type="checkbox"]').check()
    await expect(btn).toBeEnabled()
  })

  test('accepting disclaimer shows login overlay', async ({ page }) => {
    // Override auth to fail so login screen shows
    await page.route('**/api/auth/check', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: false }) }),
    )
    await page.goto('/')
    await page.locator('.disclaimer-card input[type="checkbox"]').check()
    await page.locator('.disclaimer-card .btn--primary').click()

    await expect(page.locator('.login-card')).toBeVisible()
    await expect(page.getByPlaceholder('Admin secret')).toBeVisible()
  })

  test('disclaimer is skipped after accepting', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('polyclaw_disclaimer_accepted', '1')
    })
    await page.goto('/')
    await expect(page.locator('.disclaimer-card')).not.toBeVisible()
  })
})

test.describe('Login overlay', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('polyclaw_disclaimer_accepted', '1')
    })
    await mockApi(page)
  })

  test('shows login when no token', async ({ page }) => {
    // Override auth check to fail
    await page.route('**/api/auth/check', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: false }) }),
    )
    await page.goto('/')
    await expect(page.locator('.login-card')).toBeVisible()
    await expect(page.getByText('Polyclaw')).toBeVisible()
  })

  test('sign-in button is disabled when input is empty', async ({ page }) => {
    await page.route('**/api/auth/check', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: false }) }),
    )
    await page.goto('/')
    const btn = page.locator('.login-card .btn--primary')
    await expect(btn).toBeDisabled()
  })

  test('submitting secret authenticates and shows main app', async ({ page }) => {
    // First auth check fails, second succeeds
    let authAttempt = 0
    await page.route('**/api/auth/check', route => {
      authAttempt++
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ authenticated: authAttempt > 1 }),
      })
    })

    await page.goto('/')
    await expect(page.locator('.login-card')).toBeVisible()
    await page.getByPlaceholder('Admin secret').fill('my-secret')
    await page.locator('.login-card .btn--primary').click()

    // After login, sidebar should appear
    await expect(page.locator('.sidebar')).toBeVisible()
  })

  test('extracts token from URL ?secret= parameter', async ({ page }) => {
    await page.goto('/?secret=url-token')
    // Should land in authenticated state
    await expect(page.locator('.sidebar')).toBeVisible()
  })
})
