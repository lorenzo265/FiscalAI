---
description: Roda o gate de contexto fresco no diff atual (backend e/ou frontend, conforme o que mudou)
argument-hint: "[opcional: backend | frontend]"
---

# Revisar PR / diff atual

Rode o gate de revisão de **contexto fresco** sobre o diff atual. Não pergunte confirmação — execute e reporte.

## Roteamento
1. Veja o que mudou: `git diff --name-only` + `git status`.
2. Toca `analista-fiscal-api/` → acione o subagente **backend-reviewer**.
3. Toca `analista-fiscal-web/` → acione o **reviewer** (frontend); se há tela alterada, também o **frontend-verifier**.
4. Toca os dois → rode ambos.
5. Argumento `$1` força o lado (`backend` / `frontend`).

## Saída
O veredito de cada revisor (APROVA/REPROVA + Crítico/Aviso/Sugestão). Se REPROVA, nomeie o agente dono e **não faça merge**. Write-back do veredito no `log_agente.md` (backend) ou `docs/HANDOFF.md` (frontend).
