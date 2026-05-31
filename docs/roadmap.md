---
tags: [roadmap, evolucao, sprints]
fonte: "[[PlanoBackend]] §11 + log_agente.md + trilha 100% (2026-05-27)"
atualizado: 2026-05-31
testes_atuais: 2200
sprints_concluidas: 27
sprints_extras: 7
sprints_total: 28
---

# 🗺️ Roadmap — evolução do projeto

> Fonte da verdade do progresso. **Quando uma sprint é concluída, o Claude marca aqui** (status na tabela + frontmatter da nota da sprint, se existir). Protocolo em `CLAUDE.md` → "Protocolo Obsidian + Claude Code". Hub: [[README]] · painéis: [[dashboard]].

## 📈 Onde estamos

- **Sprints concluídas:** 0–19 + 19.5 + 19.6 + 19.7 + 19.8 (24 de 28) ✅ + 4 sprints extras (15.5 + 19.5 + 19.6 + 19.7 + 19.8) ✅
- **Trilha 100% FECHADA** (pós-19.5, pré-piloto pago): **19.6 ✅ → 19.7 ✅ → 19.8 ✅** — 3 de 3 sprints extras concluídas. **100% das pendências conscientes** resolvidas ou documentadas como `[externo-runbook]` em `docs/pendencias/runbook-ativacao-externos.md`.
- **🎉 ROADMAP COMPLETO — Sprints 0–22 concluídas.** Produto completo PME-alvo pronto para 1.000+ pagantes.
- **Suite atual:** **2200 testes** passando, 2 skipped · mypy strict 0 erros · 22 sprints entregues em 4 fases.
- **Fase 3 — Sprint 19.5 entregou:** PR1 painel admin (`/v1/admin/tabelas/<tipo>/vigencia` substitui migration por POST estruturado + audit log + idempotência UUID5) → PR2 worker Celery `tabelas.verificar_vigencias` (diário 06:15 com 7 avaliadores + auto-resolução ao postar nova vigência + hook digest admin) → PR3 worker `tabelas.varrer_dou_mensal` (mensal dia 5: scraper DOU + LLM extrai → sugestão pendente com re-check §8.6 + admin aprova com 1 clique). Pendências **#9** + **#37** estruturalmente resolvidas.
- **Fase 1 (MVP, S0–6):** ✅ fechada · **Fase 2 (S7–13):** ✅ fechada · **Fase 3 (S14–20):** 🚧 14 ✅ · 15 ✅ · 15.5 ✅ · 16 ✅ · 17 ✅ · 18 ✅ · 19 ✅ · 19.5 ✅ · 19.6 ✅ · 19.7 ✅ · 19.8 ✅ · 20 🔜 · **Fase 4 (S21–22):** pendente

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
| 13 | Marketplace de contadores → [[sprints/sprint-13-marketplace]] | ✅ | 1199 |

> Hardening pós-S12 (Review + Fase 1.x + Fase 2 PR1–4): suite chegou a **992** e cravou §8.2/§8.3/§8.9 no DB. Sprint 13 (3 PRs) fecha o marketplace + auth parceiro + pagamento stub (ADR 0015) + Celery + LGPD revoke. Marco Fase 2: **50 pagantes + MRR R$10k+** — agora dependente de aquisição + ativação do provider real (pendência rastreada).

## Fase 3 — SPED + Reforma + escala (S14–20)

| Sprint | Tema | Status | Testes |
|---|---|---|---|
| 14 | Reforma Tributária (CBS/IBS informacional) → [[sprints/sprint-14-reforma]] | ✅ | 1288 |
| 15 | AI Advisor proativo → [[sprints/sprint-15-advisor]] | ✅ | 1386 |
| 15.5 | Envio real digest WhatsApp (extra) → [[sprints/sprint-15-advisor]] | ✅ | 1417 |
| 16 | SPED ECD + ECF | ✅ | 1556 |
| 17 | EFD-Contribuições + EFD ICMS-IPI | ✅ | 1604 |
| 18 | Migração de escritório antigo → [[sprints/sprint-18-migracao]] | ✅ | 1671 |
| 19 | Polish + escala (perf DB + k6 harness + cache Redis + onboarding bundle) → [[sprints/sprint-19-performance]] | ✅ | 1716 |
| 19.5 | Painel admin de tabelas tributárias (3 camadas: API admin + Celery alerta + DOU+LLM) → [[sprints/sprint-19-5-tabelas-tributarias]] | ✅ | 1821 |
| 19.6 | Housekeeping pré-piloto — 16 de 17 [risco-*] resolvidos → [[sprints/sprint-19-6-housekeeping-pre-piloto]] | ✅ | 1885 |
| 19.7 | Backlog técnico — 10 scope-cuts prioritários (eSocial transmissão real é o maior) → [[sprints/sprint-19-7-backlog-tecnico]] | ✅ | 1993 |
| 19.8 | Cleanup + runbook externos — fecha 100% das pendências ativas → [[sprints/sprint-19-8-cleanup-externos]] | ✅ | 2012 |
| 20 | Lucro Presumido pronto pra venda → [[sprints/sprint-20-lp-piloto]] | ✅ | 2121 |

> Marco Fase 3: **200 pagantes + MRR R$40k+**.

## Fase 4 — Lapidação (S21–22)

| Sprint | Tema | Status | Testes |
|---|---|---|---|
| 21 | Hardening + segurança → [[sprints/sprint-21-hardening]] | ✅ | 2187 |
| 22 | Documentação + handover → [[sprints/sprint-22-documentacao]] | ✅ | 2200 |

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
