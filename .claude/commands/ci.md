---
description: Cria ou atualiza o pipeline de CI e os gates automáticos (workflows, pre-commit, hooks)
argument-hint: "[opcional: o que ajustar]"
---

# CI / gates — $ARGUMENTS

Acione o subagente **ci-engineer** para criar/ajustar a infraestrutura de gates. Execute sem confirmar a cada passo.

## Escopo
- `.github/workflows/ci.yml` (backend-quality + backend-integration + frontend).
- `.pre-commit-config.yaml` (ruff + básicos).
- Hooks de sessão em `.claude/settings.json` (`command-guard.ps1` de freios; e, se pedido, write-back/lint).
- `$ARGUMENTS` direciona o ajuste (ex.: "adicione job de E2E Playwright", "rode bandit no PR também").

## Princípio
Os 3 níveis (hook na sessão · pre-commit no git · CI no servidor) rodam o mesmo conjunto. Nunca afrouxe um gate pra passar. Sem segredo no YAML.
