---
tags: [roadmap, evolucao, sprints]
fonte: "[[PlanoBackend]] §11 + log_agente.md"
atualizado: 2026-05-20
testes_atuais: 992
sprints_concluidas: 13
sprints_total: 23
---

# 🗺️ Roadmap — evolução do projeto

> Fonte da verdade do progresso. **Quando uma sprint é concluída, o Claude marca aqui** (status na tabela + frontmatter da nota da sprint, se existir). Protocolo em `CLAUDE.md` → "Protocolo Obsidian + Claude Code". Hub: [[README]] · painéis: [[dashboard]].

## 📈 Onde estamos

- **Sprints concluídas:** 0–12 (13 de 23) ✅
- **Próxima:** [[sprints/sprint-13-marketplace|Sprint 13 — Marketplace]] (estava pausada até o hardening da Fase 2; PRs 1–4 da Fase 2 já fechados)
- **Suite atual:** **992 testes** passando, 2 skipped · mypy strict 0 erros
- **Fase 1 (MVP, S0–6):** ✅ fechada · **Fase 2 (S7–13):** 7–12 ✅, 13 próxima · **Fase 3 (S14–20):** pendente · **Fase 4 (S21–22):** pendente

Legenda de status: ✅ concluída · 🔜 próxima · ⏳ pendente · ⏸️ pausada · 🚧 em andamento

---

## Fase 1 — MVP Fiscal Simples Nacional (S0–6)

| Sprint | Tema | Status | Testes |
|---|---|---|---|
| 0 | Setup (repo, Docker, CI, ADRs) | ✅ | — |
| 1 | Fundação multi-tenant (RLS, JWT) | ✅ | — |
| 2 | Ingestão XML + DAS SN | ✅ | 63 |
| 3 | Camada IA + eval suite | ✅ | 290 |
| 4 | RAG + memória + agenda + multa/juros | ✅ | — |
| 5 | WhatsApp + NFS-e + onboarding | ✅ | 449 |
| 6 | Compliance v1 + SERPRO + DEFIS | ✅ | 537 |

## Fase 2 — Expansão para produto pago (S7–13)

| Sprint | Tema | Status | Testes |
|---|---|---|---|
| 7 | Open Finance + conciliação → [[modulos/conciliacao]] | ✅ | 625 |
| 8 | Imobilizado + provisões trabalhistas | ✅ | 673 |
| 9 | Contábil completo | ✅ | 741 |
| 10 | Pessoal completo → [[modulos/pessoal]] | ✅ | 860 |
| 11 | Lucro Presumido + ICMS + compliance v2 → [[modulos/lucro-presumido]] | ✅ | 931 |
| 12 | Relatórios → [[modulos/relatorios]] | ✅ | 980 |
| 13 | Marketplace de contadores → [[sprints/sprint-13-marketplace]] | 🔜 | — |

> Hardening pós-S12 (Review + Fase 1.x + Fase 2 PR1–4): suite chegou a **992** e cravou §8.2/§8.3/§8.9 no DB. Marco Fase 2: **50 pagantes + MRR R$10k+**.

## Fase 3 — SPED + Reforma + escala (S14–20)

| Sprint | Tema | Status | Testes |
|---|---|---|---|
| 14 | Reforma Tributária (CBS/IBS informacional) | ⏳ | — |
| 15 | AI Advisor proativo | ⏳ | — |
| 16 | SPED ECD + ECF | ⏳ | — |
| 17 | EFD-Contribuições + EFD ICMS-IPI | ⏳ | — |
| 18 | Migração de escritório antigo | ⏳ | — |
| 19 | Polish + escala (load test 1k empresas) | ⏳ | — |
| 20 | Lucro Presumido pronto pra venda | ⏳ | — |

> Marco Fase 3: **200 pagantes + MRR R$40k+**.

## Fase 4 — Lapidação (S21–22)

| Sprint | Tema | Status | Testes |
|---|---|---|---|
| 21 | Hardening + segurança (pen test) | ⏳ | — |
| 22 | Documentação + handover | ⏳ | — |

---

## 🤖 Como o Claude marca a evolução (write-back)

Ao **concluir** uma sprint (todos os PRs fechados, pytest + mypy verdes):

1. Trocar o status da sprint nesta tabela para ✅ e preencher a coluna **Testes** com a contagem final.
2. Atualizar o frontmatter: `sprints_concluidas`, `testes_atuais`, `atualizado` (data de hoje).
3. Se existir nota da sprint em `sprints/`, marcar `status: concluida` no frontmatter dela.
4. Promover a próxima sprint para 🔜 e, se já houver nota, `status: proxima`.
5. Registrar a entrada cronológica em `log_agente.md` (contagem + o que entrou).

Isso é parte do **Definition of Done** — ver `CLAUDE.md` §"Protocolo Obsidian + Claude Code". Comando de apoio: `/fechar-sprint`.

## 📋 Notas de sprint existentes (Dataview)

```dataview
TABLE WITHOUT ID
  file.link AS "Sprint",
  fase AS "Fase",
  status AS "Status",
  marco AS "Marco"
FROM "sprints"
SORT file.name ASC
```

> Conforme novas notas de sprint forem criadas em `sprints/`, elas aparecem aqui automaticamente.

Relacionado: [[README]] · [[dashboard]] · [[review-checklist]] · [[PlanoBackend]] §11
