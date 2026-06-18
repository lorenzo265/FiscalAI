---
description: Sobe o app e verifica o frontend (visual + console + a11y + E2E) com browser
argument-hint: "[rota opcional, ex: notas]"
---

# Verificar frontend $1

Acione o subagente **frontend-verifier** para verificar o frontend de verdade (não só build). Execute sem confirmar a cada passo.

## Escopo
- Sem argumento: rotas-chave (home, notas, fiscal, onboarding) + dark mode.
- Com `$1` (ex.: `notas`, `fiscal/simulador`): foca a rota.

## O que roda
1. Sobe o app (`npm run dev` ou `Claude_Preview`).
2. Screenshot por rota (gates anti-slop) + console (hidratação) + a11y (foco / contraste / cor+ícone+palavra).
3. E2E Playwright nos fluxos (wizard NF, onboarding) quando aplicável.

## Saída
Veredito por rota (Visual / Console / a11y / E2E) + achados + dono a corrigir. Write-back em `docs/HANDOFF.md`.

> Requer os MCPs de browser ativos (reiniciar a sessão + aprovar o `.mcp.json`).
