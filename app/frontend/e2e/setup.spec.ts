import { test, expect } from '@playwright/test'
import { mockApi, bypassAuth, MOCK_STATUS_NEEDS_SETUP } from './helpers'

test.describe('Setup Wizard', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders wizard with three steps', async ({ page }) => {
    await page.goto('/setup')
    await expect(page.getByAltText('octoclaw')).toBeVisible()
    // Step labels are always visible regardless of current step
    await expect(page.getByText('Azure Authentication').first()).toBeVisible()
    await expect(page.getByText('GitHub Copilot Auth')).toBeVisible()
    await expect(page.getByText('Configuration').first()).toBeVisible()
  })

  test('Azure step shows sign-in button when not logged in', async ({ page }) => {
    await page.route('**/api/setup/status', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_STATUS_NEEDS_SETUP) }),
    )
    await page.goto('/setup')
    await expect(page.getByRole('button', { name: 'Sign in with Azure CLI' })).toBeVisible()
  })

  test('Azure step shows authenticated badge when logged in', async ({ page }) => {
    await page.goto('/setup')
    // Default mock has azure logged in, but wizard auto-advances.
    // Click Azure step button to go back
    await page.locator('.setup__step', { hasText: 'Azure Authentication' }).click()
    await expect(page.locator('.badge--ok', { hasText: 'Authenticated' })).toBeVisible()
  })

  test('clicking Azure sign-in sends POST', async ({ page }) => {
    await page.route('**/api/setup/status', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_STATUS_NEEDS_SETUP) }),
    )
    let loginCalled = false
    await page.route('**/api/setup/azure/login', route => {
      loginCalled = true
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
    })

    await page.goto('/setup')
    await page.getByRole('button', { name: 'Sign in with Azure CLI' }).click()
    expect(loginCalled).toBe(true)
  })

  test('navigating to config step shows form fields', async ({ page }) => {
    await page.goto('/setup')
    // Click on Configuration step label (auto-advance may already be there)
    await page.locator('.setup__step', { hasText: 'Configuration' }).click()
    await expect(page.getByText('Bot Configuration')).toBeVisible()
    await expect(page.getByPlaceholder('Azure Bot App ID')).toBeVisible()
    await expect(page.getByPlaceholder('Azure Bot App Password')).toBeVisible()
  })

  test('submitting config step sends POST', async ({ page }) => {
    let saveCalled = false
    await page.route('**/api/setup/configuration/save', route => {
      saveCalled = true
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
    })

    await page.goto('/setup')
    // Click on Configuration step to navigate there
    await page.locator('.setup__step', { hasText: 'Configuration' }).click()
    await expect(page.getByText('Bot Configuration')).toBeVisible()
    await page.getByPlaceholder('Azure Bot App ID').fill('test-app-id')
    await page.getByPlaceholder('Azure Bot App Password').fill('test-password')
    await page.getByRole('button', { name: 'Save Configuration' }).click()
    expect(saveCalled).toBe(true)
  })

  test('shows completion state when all steps done', async ({ page }) => {
    await page.goto('/setup')
    await expect(page.getByText('Setup complete')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start Chatting' })).toBeVisible()
  })
})
