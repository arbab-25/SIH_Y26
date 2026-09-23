import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright e2e config (Phase 5). The suite targets a RUNNING environment:
 * E2E_BASE_URL (default http://localhost:5173). Tests self-skip when
 * E2E_TEST_EMAIL/E2E_TEST_PASSWORD are unset, so `npm run e2e` never fails
 * merely because no seeded account exists.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chrome', use: { ...devices['Pixel 7'] } },
  ],
});
