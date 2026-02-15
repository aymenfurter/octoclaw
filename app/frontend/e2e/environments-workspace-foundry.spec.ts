import { test, expect } from '@playwright/test'
import { mockApi, bypassAuth } from './helpers'

test.describe('Environments page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/environments')
    await expect(page.getByRole('heading', { name: 'Environments' })).toBeVisible()
  })

  test('displays deployments table', async ({ page }) => {
    await page.goto('/environments')
    await expect(page.locator('table.table')).toBeVisible()
    await expect(page.getByText('dep-001')).toBeVisible()
    await expect(page.getByText('v3.0.0')).toBeVisible()
  })

  test('shows status badge', async ({ page }) => {
    await page.goto('/environments')
    await expect(page.getByText('active')).toBeVisible()
  })

  test('clicking row shows detail panel', async ({ page }) => {
    await page.goto('/environments')
    await page.getByText('dep-001').click()
    await expect(page.getByRole('button', { name: 'Destroy' })).toBeVisible()
  })

  test('detail panel shows resources', async ({ page }) => {
    await page.goto('/environments')
    await page.getByText('dep-001').click()
    await expect(page.getByText('ContainerApp')).toBeVisible()
    await expect(page.getByText('octoclaw-app')).toBeVisible()
  })

  test('audit button sends POST', async ({ page }) => {
    let auditCalled = false
    await page.route('**/api/environments/audit', route => {
      auditCalled = true
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ tracked_resources: [], orphaned_resources: [], orphaned_groups: [] }),
      })
    })
    await page.goto('/environments')
    await page.getByRole('button', { name: 'Run Audit' }).click()
    expect(auditCalled).toBe(true)
  })

  test('audit results show no orphans message', async ({ page }) => {
    await page.goto('/environments')
    await page.getByRole('button', { name: 'Run Audit' }).click()
    await expect(page.getByText('No orphaned resources found')).toBeVisible()
  })

  test('empty state when no deployments', async ({ page }) => {
    await page.route('**/api/environments', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ deployments: [] }) }),
    )
    await page.goto('/environments')
    await expect(page.getByText('No deployments registered')).toBeVisible()
  })
})

test.describe('Workspace page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/workspace')
    await expect(page.getByRole('heading', { name: 'Workspace' })).toBeVisible()
  })

  test('shows breadcrumb', async ({ page }) => {
    await page.goto('/workspace')
    await expect(page.locator('.breadcrumb')).toBeVisible()
    await expect(page.getByText('data')).toBeVisible()
  })

  test('lists directory entries', async ({ page }) => {
    await page.goto('/workspace')
    await expect(page.getByText('sessions')).toBeVisible()
    await expect(page.getByText('config.json')).toBeVisible()
    await expect(page.getByText('profile.json')).toBeVisible()
  })

  test('directory entries show folder icon', async ({ page }) => {
    await page.goto('/workspace')
    const dirEntry = page.locator('.workspace-entry--dir', { hasText: 'sessions' })
    await expect(dirEntry).toBeVisible()
  })

  test('file entries show size', async ({ page }) => {
    await page.goto('/workspace')
    await expect(page.getByText('1.0 KB')).toBeVisible()
  })

  test('clicking file shows preview', async ({ page }) => {
    await page.goto('/workspace')
    await page.getByText('config.json').click()
    await expect(page.locator('.workspace-preview')).toBeVisible()
    await expect(page.locator('.workspace-preview').getByText('"key"')).toBeVisible()
  })

  test('clicking directory navigates', async ({ page }) => {
    await page.goto('/workspace')
    await page.locator('.workspace-entry--dir', { hasText: 'sessions' }).click()
    // Breadcrumb should update
    await expect(page.locator('.breadcrumb')).toContainText('sessions')
  })

  test('empty directory shows message', async ({ page }) => {
    await page.route('**/api/workspace/list*', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', entries: [] }) }),
    )
    await page.goto('/workspace')
    await expect(page.getByText('Empty directory')).toBeVisible()
  })
})

test.describe('Foundry IQ page', () => {
  test.beforeEach(async ({ page }) => {
    await bypassAuth(page)
    await mockApi(page)
  })

  test('renders page title', async ({ page }) => {
    await page.goto('/foundry-iq')
    await expect(page.getByRole('heading', { name: 'Foundry IQ' })).toBeVisible()
  })

  test('shows stats bar', async ({ page }) => {
    await page.goto('/foundry-iq')
    const statsBar = page.locator('.stats-bar')
    await expect(statsBar).toBeVisible()
    await expect(statsBar.getByText('Status')).toBeVisible()
    await expect(statsBar.getByText('Documents')).toBeVisible()
    await expect(statsBar.getByText('Schedule')).toBeVisible()
  })

  test('shows configuration form', async ({ page }) => {
    await page.goto('/foundry-iq')
    await expect(page.getByText('Configuration')).toBeVisible()
    await expect(page.getByText('Search Endpoint')).toBeVisible()
    await expect(page.getByText('Embedding Endpoint')).toBeVisible()
  })

  test('enable checkbox is checked', async ({ page }) => {
    await page.goto('/foundry-iq')
    const checkbox = page.locator('input[type="checkbox"]')
    await expect(checkbox).toBeChecked()
  })

  test('save config sends PUT and POST', async ({ page }) => {
    let putCalled = false
    let indexCalled = false
    await page.route('**/api/foundry-iq/**', route => {
      const url = route.request().url()
      if (url.includes('/foundry-iq/config') && route.request().method() === 'PUT') {
        putCalled = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      }
      if (url.includes('/foundry-iq/ensure-index')) {
        indexCalled = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      }
      if (url.includes('/foundry-iq/stats')) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', document_count: 150, index_missing: false }) })
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', enabled: true, search_endpoint: 'https://search.example.com', index_name: 'octoclaw-memories', embedding_endpoint: 'https://embedding.example.com', embedding_model: 'text-embedding-3-large', embedding_dimensions: 3072, index_schedule: 'daily', provisioned: false }) })
    })
    await page.goto('/foundry-iq')
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/foundry-iq/ensure-index')),
      page.getByRole('button', { name: 'Save & Create Index' }).click(),
    ])
    expect(putCalled).toBe(true)
    expect(indexCalled).toBe(true)
  })

  test('run indexing button calls API', async ({ page }) => {
    let indexCalled = false
    await page.route('**/api/foundry-iq/index', route => {
      indexCalled = true
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ status: 'ok', indexed: 10, total_files: 5, total_chunks: 50 }),
      })
    })
    await page.goto('/foundry-iq')
    await page.getByRole('button', { name: 'Run Indexing' }).click()
    expect(indexCalled).toBe(true)
  })

  test('search memories returns results', async ({ page }) => {
    await page.goto('/foundry-iq')
    await page.getByPlaceholder('Search your memories...').fill('test query')
    await page.getByRole('button', { name: 'Search' }).click()
    await expect(page.getByText('Test Doc')).toBeVisible()
    await expect(page.getByText('Test content for search result')).toBeVisible()
  })

  test('search with empty query does nothing', async ({ page }) => {
    let searchCalled = false
    await page.route('**/api/foundry-iq/search', route => {
      searchCalled = true
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', results: [] }) })
    })
    await page.goto('/foundry-iq')
    await page.getByRole('button', { name: 'Search' }).click()
    expect(searchCalled).toBe(false)
  })
})
