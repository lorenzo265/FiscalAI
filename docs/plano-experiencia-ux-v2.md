# Plano Experiência — Sequência única de PRs (auditoria UX × identidade v2)
## 2026-06-16 | Modo: [PLAN] frontend | Detalha o Squad Experiência do `PLANO_PRODUCTION_READY.md` (§4/§6)

Funde dois contratos que se sobrepõem nas **mesmas telas**:

- **`legacy/auditoria-ux-frontend-2026.md`** — 12 mudanças de usabilidade (linguagem, hierarquia, fluxo, confiança), pensadas sobre a pele v1 "Instrumento".
- **`arkan-claro-identidade-v2.md`** — fases D0–D6 que **recalibram os tokens** para a v2 "Arkan Claro" (clareza Apple: número-herói, mais respiro, blueprint vira assinatura rara).

Sem conciliação, há retrabalho garantido: pintar a home "3 respostas" na pele v1 (S2) e repintá-la com número-herói na v2 (S6) é construir a mesma tela duas vezes. Este doc define a ordem que evita isso. **Não substitui** o plano-mãe — refina o nível PR-a-PR; em conflito, `PLANO_PRODUCTION_READY.md` vence.

---

## Regra-mãe: conteúdo antes da forma

Cada uma das 12 mudanças cai em uma de três trilhas, e a trilha decide **quando** ela entra:

| Trilha | O que é | Depende dos tokens v2? | Quando entra |
|---|---|---|---|
| **A — Conteúdo/Linguagem** | traduções, apostos, mensagens de erro, classificação de urgência | ❌ Não | **Já** (S1–S2), zero retrabalho |
| **B — Fluxo/Wiring** | onboarding CNPJ-first, assistente real (ligar ao backend) | ❌ Não (consome primitivas quando prontas) | Paralelo (S6) |
| **C — Forma/Layout** | número-herói, régua, cards no mobile, ação primária, Carimbo como rito | ✅ Sim | **Junto da v2** (S3→S7), nunca antes |

> **Nunca se pinta uma tela na pele v1 para repintá-la na v2.** Layout só se materializa depois que os tokens v2 existem (D1). O que vem antes é tudo que sobrevive à troca de pele: palavra, dado, lógica, ordem.

A única mudança que **se divide** entre trilhas é a Home (nº 4): a *ordem das 3 respostas e seus dados* (Trilha A, S2) vem antes; a *forma* — número-herói + régua + count-up (Trilha C, S6) — recalibra, não reconstrói.

---

## A sequência única de PRs

Sprints (S1–S12) e marcos (M1–M6) são os do `PLANO_PRODUCTION_READY.md §6`.

### Bloco 0 — Conteúdo (S1) · Trilha A · zero dependência de tokens
- **PR-X1 — Tradução de obrigações.** `lib/traducao/obrigacoes.ts` central (DAS→"Guia mensal de impostos" · PGDAS-D→"Declaração do faturamento do mês" · DEFIS · eSocial · DCTFWeb), padrão frase-PT + sigla em `<abbr>` mono. Consumir em agenda, home, fiscal, notificações. + apostos de tributo no health score (ICMS/ISS/INSS/FGTS) + Fator R/Anexo traduzidos para o **efeito**, com termo técnico só em "ver detalhe". *(mudanças 1, 2-linguagem, 3)*
- **PR-X2 — Erros que dizem o que fazer.** `lib/traducao/erros.ts`: ~60 `DomainError` → frase humana; `ErrorState` sempre "o que houve (PT) + o que fazer + botão da ação"; nunca expor stack. *(mudança 9)*
- **PR-X3 — Urgência em 3 níveis (lógica).** Classificador de prazo (≤3d 🔴 / ≤7d 🟠 / >7d neutro) + `Pill` cor+ícone+palavra na agenda e na home. *(mudança 5-lógica)*

*DoD bloco (= DoD S1): zero sigla crua em agenda/home; todo erro acionável; urgência diferenciada visível.*

### Bloco 1 — Resposta de 5s em dados (S2) · Trilha A · ordenação/wiring, ainda pele v1
- **PR-X4 — Home = 3 respostas (dados + ordem).** Nesta ordem, nada antes: (1) "Estou bem?" health score; (2) "O que pago agora?" próximo vencimento com valor + ação única "Pagar guia"; (3) "Quanto este mês?" imposto estimado. Rebaixar widgets que não respondem às 3 perguntas. Card de urgência ≤3d fixo no topo. **Forma ainda a atual — a recalibração visual é o Bloco 4.** *(mudanças 4a, 5-home)*

*DoD (= M1): home responde "estou bem / o que pago / quanto" em 5s.*

### Bloco 2 — Tokens v2 (S3) · D0 + D1
- **PR-X5 — [EXTRACT].** Teardown de 3 referências (1 Apple, 1 ferramenta premium clara, 1 banking BR) → leis sintetizadas em `docs/`, zero cópia. *(D0)*
- **PR-X6 — `@theme` v2 + dark re-derivado + `/showcase`.** Valores do §2 da identidade v2 (papel mais claro, card plano, radius 6/10/16, springs). Gate anti-slop v2 verde; AA nos 2 temas; build verde. *(D1)*

### Bloco 3 — Primitivas v2 (S4) · D2 + D3 · aqui entram as mudanças de **forma**
- **PR-X7 — Passada nas 24 primitivas (`ui/*` + `shared/*`).** Deltas §3: botão primário verde 44px (resolve a11y da Fase 2 **e** a "ação primária por tela"), tabela→card no mobile como padrão da primitiva, `Ruler` evoluída (base dos monitores), `useCountUp`, tab bar inferior mobile no shell. API preservada; invariantes §7. *(mudanças 7-primitiva, 10-primitiva)*
- **PR-X8 — Gabarito Notas recalibrado v2.** Exercita número-herói, ação primária única, **Carimbo pós-ação**, card no mobile. Reviewer de contexto fresco aprova os gates v2; "5 segundos" testado. *(mudança 12-padrão; D3)*

*DoD: gabarito v2 aprovado; primitivas com Lighthouse a11y ≥95 no showcase.*

### Bloco 4 — Telas v2 + home definitiva (S5–S6) · D4
- **PR-X9 — Home v2 (forma).** Número-herói mono 56–72px no valor que responde a tela, régua de limite, count-up, urgência recalibrada. **Recalibra o PR-X4 — não reconstrói.** *(mudança 4b)*
- **PR-X10…X13 — Lotes A/C/D/E imitam o gabarito.** Por domínio: ação primária por tela em verbo do dono, cards no mobile, Carimbo pós-ação. *(mudanças 7, 10, 12 — aplicação)*
- **PR-X14 — "Fechar o mês" guiado** com Carimbo no fim (casado com a orquestração fiscal eSocial→Reinf→DCTFWeb da S5). *(mudança 12 — aplicação)*

### Bloco 5 — Fluxo (S6) · Trilha B · paralelo aos lotes
- **PR-X15 — Onboarding CNPJ-first.** Passo 1 só CNPJ → BrasilAPI pré-preenche (razão social, CNAE, regime) → dashboard imediato com o inferível → pedir resto (certificado, banco) **em contexto** → persistir progresso (Dexie/localStorage). *(mudança 8)*
- **PR-X16 — Assistente real.** Ligar ao backend `assistente` (citação obrigatória já pronta), onipresente, com perguntas prontas contextuais ("Por que meu imposto subiu?"). Enquanto mock, **esconder o botão**. *(mudança 11)*

*DoD (= M3): onboarding <10 min sem ajuda; assistente respondendo com citação.*

### Bloco 6 — Limites, marca, polish (S7 · S8 · S11)
- **PR-X17 — Monitores de limite (S7).** Régua v2 contra R$81k / R$3,6M / R$4,8M com projeção ("no seu ritmo: outubro") + fluxo desenquadramento MEI→ME e sublimite + medidor visual do Fator R. *(mudanças 6, 2-widget)*
- **PR-X18 — Brand pack (S8/D5):** logo final, landing (hero = produto real), social, e-mail transacional, brand book.
- **PR-X19 — Motion polish final (S11/D6):** springs calibrados em device real, dark validado por humano, Lighthouse ≥95 a11y/perf.

---

## Rastreabilidade

**As 12 mudanças da auditoria UX → PR:**

| # | Mudança | Trilha | PR | Sprint |
|---|---|---|---|---|
| 1 | Traduzir obrigações (`obrigacoes.ts`) | A | X1 | S1 |
| 2 | Fator R / Anexo: efeito, não termo | A (ling.) + C (widget) | X1 / X17 | S1 / S7 |
| 3 | Apostos nos tributos do health score | A | X1 | S1 |
| 4 | Home = 3 respostas | A (ordem) + C (forma) | X4 / X9 | S2 / S6 |
| 5 | Urgência em 3 níveis | A (lógica) + C (home) | X3 / X4 | S1 / S2 |
| 6 | Monitores de limite (`Ruler`) | C | X17 | S7 |
| 7 | Uma ação primária por tela | C | X7 (prim.) / X10–13 (aplic.) | S4 / S5–S6 |
| 8 | Onboarding CNPJ-first | B | X15 | S6 |
| 9 | Erros que dizem o que fazer (`erros.ts`) | A | X2 | S1 |
| 10 | Tabelas → cards no mobile | C | X7 (prim.) / X10–13 (aplic.) | S4 / S5–S6 |
| 11 | Assistente real | B | X16 | S6 |
| 12 | Confirmação com prova (Carimbo) | C | X8 (gabarito) / X10–14 (aplic.) | S4 / S5–S6 |

**As fases D0–D6 da identidade v2 → PR:**

| Fase v2 | PR | Sprint |
|---|---|---|
| D0 Extract | X5 | S3 |
| D1 Tokens | X6 | S3 |
| D2 Primitivas | X7 | S4 |
| D3 Gabarito | X8 | S4 |
| D4 Lotes + home | X9–X13 | S5–S6 |
| D5 Marca | X18 | S8 |
| D6 Polish | X19 | S11 |

---

## O que este plano NÃO autoriza
- Construir layout na pele v1 que a v2 vai refazer (viola a regra-mãe). Forma só depois de D1.
- Quebrar invariante de função ao revestir (hooks/providers/Dexie/wizards/PDF/charts intactos — `CLAUDE.md` §Invariantes).
- Reintroduzir dark/neon, segundo acento, sigla sem tradução, ou Carimbo/crop-marks como moldura comum (inflação da assinatura — gate v2 §5).
- Divergir das sprints/marcos do `PLANO_PRODUCTION_READY.md`.

---

**Processo (herda o que funcionou na v1):** HANDOFF append-only · reviewer de contexto fresco em todo PR (gates anti-slop v2 + invariantes §7) · screen-implementers no tree principal · gabarito (Notas) antes dos lotes.
