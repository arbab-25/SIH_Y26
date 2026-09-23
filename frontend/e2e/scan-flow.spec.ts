import { test, expect } from '@playwright/test';

/**
 * Playwright e2e (Phase 5): the three critical journeys.
 *
 * Runs against a LIVE backend: set E2E_BASE_URL (default http://localhost:5173)
 * and E2E_TEST_EMAIL / E2E_TEST_PASSWORD for an account seeded in that
 * environment. The tests are skipped (not failed) when no account is
 * configured, so CI without a seeded backend stays green.
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const EMAIL = process.env.E2E_TEST_EMAIL || '';
const PASSWORD = process.env.E2E_TEST_PASSWORD || '';

const needsAccount = test.skip(!EMAIL || !PASSWORD, 'E2E_TEST_EMAIL/E2E_TEST_PASSWORD not configured');
void needsAccount;

test.use({ baseURL: BASE_URL });

test.describe('login journey', () => {
  test('sign-in page accepts seeded inspector credentials', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText(/CODE MAZE/i).first()).toBeVisible();

    if (!EMAIL || !PASSWORD) {
      test.skip(true, 'account not configured');
    }

    await page.getByRole('button', { name: /sign in|log ?in/i }).first().click();
    await page.getByPlaceholder(/email|mobile/i).fill(EMAIL);
    await page.getByPlaceholder(/password/i).fill(PASSWORD);
    await page.getByRole('button', { name: /sign in|log ?in|प्रवेश/i }).last().click();

    // Signed-in header shows the inspector identity (name or Sign Out control).
    await expect(page.getByRole('button', { name: /sign out|log ?out/i })).toBeVisible({
      timeout: 10_000,
    });
  });
});

test.describe('scan journey', () => {
  test('upload a label image and reach a verdict', async ({ page }) => {
    test.skip(!EMAIL || !PASSWORD, 'account not configured');

    await page.goto('/');
    await page.getByRole('button', { name: /sign in|log ?in/i }).first().click();
    await page.getByPlaceholder(/email|mobile/i).fill(EMAIL);
    await page.getByPlaceholder(/password/i).fill(PASSWORD);
    await page.getByRole('button', { name: /sign in|log ?in|प्रवेश/i }).last().click();
    await expect(page.getByRole('button', { name: /sign out|log ?out/i })).toBeVisible();

    // Upload the committed synthetic label (rendered by tests/benchdata).
    const fileInput = page.locator('input[type="file"]').nth(1); // gallery input
    await fileInput.setInputFiles({
      name: 'label.png',
      mimeType: 'image/png',
      buffer: Buffer.from(
        `iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==`,
        'base64',
      ),
    });

    await page.getByRole('button', { name: /analyze|विश्लेषण/i }).click();

    // The deterministic pipeline progress card appears, then a verdict.
    await expect(page.getByText(/deterministic pipeline|निर्धारित प्रक्रिया/i)).toBeVisible({
      timeout: 5_000,
    });
    await expect(
      page.getByText(/COMPLIANT|NON-?COMPLIANT|NEEDS REVIEW|अनुपालित|गैर-अनुपालित|समीक्षा/i).first()
    ).toBeVisible({ timeout: 120_000 });
  });
});

test.describe('report download journey', () => {
  test('generate report and download its PDF', async ({ request }) => {
    test.skip(!EMAIL || !PASSWORD, 'account not configured');

    // Login via API for a token (faster than UI round-trip).
    const login = await request.post('/api/v1/auth/login', {
      data: { identifier: EMAIL, password: PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
    const { token } = (await login.json()).token;

    // Pick any existing scan; skip cleanly when the env has none.
    const scans = await request.get('/api/v1/scans?page=1&size=1', {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(scans.ok()).toBeTruthy();
    const items = (await scans.json()).items || [];
    test.skip(items.length === 0, 'no scans in the target environment');

    const report = await request.post('/api/v1/reports', {
      data: { scan_id: items[0].id },
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(report.status()).toBe(201);
    const reportBody = await report.json();

    // Download the PDF through the share token (no auth header needed).
    const pdf = await request.get(
      `/api/v1/reports/${reportBody.report_number}/pdf?share_token=${reportBody.share_token}`
    );
    expect(pdf.ok()).toBeTruthy();
    expect(pdf.headers()['content-type']).toContain('application/pdf');
    const body = await pdf.body();
    expect(body.length).toBeGreaterThan(500);
    expect(body.subarray(0, 5).toString()).toContain('%PDF');
  });
});
