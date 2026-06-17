import { defineConfig, devices } from "@playwright/test";

/**
 * playwright.config.ts — Configuração para testes visuais e de acessibilidade.
 *
 * Cobre dois conjuntos de testes:
 *   tests/visual/   — screenshot regression (toHaveScreenshot)
 *   tests/a11y/     — axe-core via @axe-core/playwright
 *
 * Baseline de screenshots fica em:
 *   tests/visual/snapshots/<test-name>-<browser>-<platform>.png
 * (commitar o diretório snapshots/ para git-tracking do baseline)
 *
 * Para gerar/atualizar baseline localmente:
 *   npx playwright test tests/visual/ --update-snapshots
 */

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./tests",
  testMatch: ["tests/visual/**/*.spec.ts", "tests/a11y/**/*.spec.ts"],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Inicia o servidor Next.js antes dos testes (CI: build estático já existe)
  webServer: {
    command: process.env.CI ? "npm run start" : "npm run dev",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },

  // Diretório base para screenshots de regressão visual
  snapshotDir: "tests/visual/snapshots",
  // Tolerância de diferença pixel (ajustar após baseline)
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.02,
      threshold: 0.2,
    },
  },
});
