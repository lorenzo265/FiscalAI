---
description: Fecha uma sprint — roda gates, marca evolução no roadmap e faz write-back no vault
argument-hint: "[número da sprint, ex: 13]"
---

# Fechar sprint $1

Execute o protocolo de Definition of Done da sprint $1. Não pergunte confirmação a cada passo — execute e reporte ao final.

## 1. Gates obrigatórios (bloqueiam o fechamento)

```powershell
$env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
cd C:\dev\Apresentação-Ideia\analista-fiscal-api
poetry run python -m pytest tests/unit tests/eval
poetry run python -m mypy app/
```

Se pytest falhar ou mypy acusar erro, pare e reporte — a sprint não fecha. Anote a contagem final de testes.

## 2. Auto-review contra os princípios

Revise o diff da sprint contra `docs/review-checklist.md`. Marque cada item como ok/falha/n.a. e justifique as falhas. Violação de princípio bloqueia o fechamento igual a teste vermelho.

## 3. Marcar a evolução em docs/roadmap.md

- Status da Sprint $1 na tabela vira concluída e a coluna Testes recebe a contagem final do passo 1.
- Frontmatter do roadmap.md: sprints_concluidas +1, testes_atuais = contagem final, atualizado = data de hoje (use `date +%F`).
- Promover a próxima sprint para o status de próxima.

## 4. Write-back no vault (docs/)

- Se existir docs/sprints/sprint-$1-*.md, marcar status: concluida no frontmatter; na nota da próxima sprint, status: proxima.
- Pendências resolvidas nesta sprint viram status: resolvida nas notas em docs/pendencias/.
- Decisão arquitetural nova vira docs/decisoes/adr-XXX-*.md, linkada no docs/README.md.
- Módulo novo vira docs/modulos/<nome>.md, linkado no docs/README.md.

## 5. Log + verificação

- Adicionar entrada em log_agente.md (contagem de testes + o que entrou na sprint).
- Verificar que nenhum wikilink ficou quebrado em docs/.

## 6. Reportar

Resumo final em português: contagem de testes (antes -> depois), status do mypy, itens da checklist, o que foi marcado no roadmap, e qual é a próxima sprint. Sugerir o próximo passo, mas esperar `prossiga` para começar a próxima.
