/**
 * Testes de acessibilidade com @axe-core/playwright.
 *
 * Verifica conformidade WCAG 2.1 AA nas rotas principais.
 * Imprime cada violação com: id, impact, description, nodes afetados.
 *
 * Dependência: npm i -D @axe-core/playwright
 */

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ROUTES = [
  { name: "homepage", path: "/" },
  { name: "dashboard", path: "/dashboard" },
  { name: "notas", path: "/notas" },
  { name: "onboarding-cnpj", path: "/onboarding/cnpj" },
];

for (const route of ROUTES) {
  test(`a11y: ${route.name} (${route.path}) — sem violações críticas`, async ({ page }) => {
    await page.goto(route.path);
    await page.waitForLoadState("networkidle");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    // Registra todas as violações para facilitar debugging no CI
    if (results.violations.length > 0) {
      console.log(`\n[axe] Violations em ${route.path}:`);
      results.violations.forEach((v) => {
        console.log(`  [${v.impact}] ${v.id}: ${v.description}`);
        v.nodes.forEach((n) => console.log(`    → ${n.html}`));
      });
    }

    // Bloqueia apenas violations de impact "critical" ou "serious"
    const blocking = results.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact ?? "")
    );

    expect(
      blocking,
      `${blocking.length} violação(ões) critical/serious em ${route.path}`
    ).toHaveLength(0);
  });
}
