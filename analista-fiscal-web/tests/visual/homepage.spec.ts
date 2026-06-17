/**
 * Teste de regressão visual — Homepage / Dashboard.
 *
 * Fluxo:
 *   1. Navega para a rota.
 *   2. Aguarda hidratação (networkidle).
 *   3. Compara com screenshot baseline.
 *
 * Para gerar o baseline inicial:
 *   npx playwright test tests/visual/ --update-snapshots
 * Depois commitar o diretório tests/visual/snapshots/ no git.
 */

import { test, expect } from "@playwright/test";

test.describe("Visual regression — páginas principais", () => {
  test("homepage renderiza conforme baseline", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // Esconde elementos dinâmicos (relógio, datas) para snapshot estável
    await page.evaluate(() => {
      document
        .querySelectorAll("[data-testid='dynamic-date'], [data-testid='clock']")
        .forEach((el) => ((el as HTMLElement).style.visibility = "hidden"));
    });
    await expect(page).toHaveScreenshot("homepage.png", {
      fullPage: true,
    });
  });

  test("dashboard renderiza conforme baseline", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("dashboard.png", {
      fullPage: true,
    });
  });

  test("tela de notas renderiza conforme baseline", async ({ page }) => {
    await page.goto("/notas");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("notas.png", {
      fullPage: true,
    });
  });
});
