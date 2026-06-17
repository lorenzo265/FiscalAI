# PLANO PRODUCTION-READY — Arkan
## 2026-06-11 | Horizonte: 6 meses (12 sprints de 2 semanas) | Lançamento em 2 fases: beta contadores → público

Fontes de verdade que este plano consolida: `legacy/validacao-cobertura-mei-simples-2026.md` (gaps fiscais), `legacy/auditoria-ux-frontend-2026.md` (12 mudanças de UX), `docs/HANDOFF.md` (re-engenharia Arkan concluída), `log_agente.md` (pendências conscientes), `docs/PlanoBackend.md` (sprints 0–22 ✅).

---

## §1 — Definição de "Production-Ready" (o contrato de saída)

O projeto está pronto para lançar quando TODOS os itens abaixo forem verdade:

| # | Critério | Verificação |
|---|---|---|
| P1 | Toda obrigação mensal do ICP (DAS, PGDAS-D, folha, eSocial→Reinf→DCTFWeb) executa ponta a ponta com transmissão real | teste E2E em staging com empresa real |
| P2 | NFS-e Nacional (ADN) emitindo — a nota do próprio público-alvo | nota autorizada em produção restrita |
| P3 | Zero sigla sem tradução; toda tela responde sua pergunta em 5s; usável a 375px | gate de aceite UX por tela (auditoria §4) |
| P4 | Infra de produção: deploy sa-east-1, CI/CD, backups testados (restore!), observabilidade ligada, rate limiting | runbook executado |
| P5 | Segurança/LGPD: RLS pen-testado, AgentShield no CI, AES-256 em repouso, termos + política de privacidade | relatório de segurança |
| P6 | Billing funcionando (assinatura, trial, cobrança, nota da própria assinatura) | primeira cobrança real |
| P7 | Onboarding self-service por CNPJ em <10 min sem ajuda humana | teste com usuário leigo |
| P8 | Suporte operacional: helpdesk, e-mail transacional, status page, runbooks de incidente | simulação de incidente |
| P9 | CBS/IBS preparado para 2027 (campos NT 2025.002 prontos, atrás de feature flag) | golden tests dos novos campos |
| P10 | 10+ empresas em beta com contadores por ≥4 semanas sem incidente fiscal | log do beta |

---

## §2 — Estado de partida (baseline 2026-06-11)

**Forte:** backend com 33 módulos, 2520 testes, mypy strict, RLS, SCD Type 2, golden tests; frontend re-vestido (identidade Arkan, ~45 rotas, tradução CFOP/CST/NCM, AA nos 2 temas); integração front-back real em 10 domínios.

**Gaps que bloqueiam lançamento** (das auditorias): NFS-e Nacional/ADN ❌ · transmissão eSocial real ❌ · cadeia Reinf→DCTFWeb não orquestrada 🟡 · tabelas 2026 pendentes (aguarda Portaria) 🟡 · Celery opt-in 🟡 · storage S3 ❌ · billing ❌ · CRF/CNDT placeholder 🟡 · assistente mock no front 🟡 · onboarding sem CNPJ-first 🟡 · jargão fiscal na agenda/home 🟡 · CBS/IBS só educacional 🟡.

---

## §3 — A equipe (divisão de funções, modelo tech lead)

**Lorenzo = Product Owner + Tech Lead humano.** Decide escopo, aprova merges de risco, executa atos com cartório/governo (certificado, credenciamentos SERPRO/Focus/ADN, contratos). Tudo mais é executado pela frota Claude Code, organizada em 4 squads. O **orquestrador** (sessão principal, lê `CLAUDE.md`) faz o papel de engineering manager: quebra a sprint em tarefas, despacha subagentes, cobra gates.

### Squads e seus agentes

| Squad | Missão | Agentes (`.claude/agents/` + ECC) | Contratos que segue |
|---|---|---|---|
| **Fiscal Core** | Cálculo e obrigações: NFS-e, eSocial, DCTFWeb, CBS/IBS, tabelas | `fiscalai-backend` (dev sênior), `analista-fiscal-br` (domínio), ECC `python` rules + `tdd` skill | `PlanoBackend.md` §8, golden tests |
| **Plataforma** | Infra, integrações externas, Celery, S3, billing, deploy | novo agente `platform-dev`, ECC `security-reviewer`, `database-optimization` | princípio §8.9 idempotência, runbooks |
| **Experiência** | Identidade v2, design system, telas, UX, landing | `frontend-design-architect` (design), `screen-implementer`, `shell`, `motion-polish`, ECC `typescript-reviewer` | `arkan-visual-style-merge.md` v2, gates anti-slop |
| **Qualidade** | Review, segurança, E2E, beta, docs | `reviewer` (contexto fresco), ECC AgentShield (`/security-scan`), novo `e2e-tester`, `docs-keeper` (vault Obsidian) | `review-checklist.md`, P1–P10 |

**Regra de ouro herdada do HANDOFF:** subagentes de tela rodam no tree principal (worktree com base `main` não enxerga o design system); coordenação por arquivos (`HANDOFF.md` frontend, `log_agente.md` backend), reviewer de contexto fresco em todo PR.

### Como o ECC (github.com/affaan-m/ecc) entra

Instalar via plugin Claude Code com perfil seletivo (não empilhar métodos de install): rules `common/` + `python/` + `typescript/`, e os módulos que pagam aluguel aqui:

- **`/multi-plan` → `/multi-execute`** — planejamento e despacho paralelo de cada sprint (espelha nossa frota; o orquestrador continua dono do merge).
- **`/quality-gate`** — gate pré-merge somado ao nosso checklist (pytest + mypy + gates anti-slop).
- **`/security-scan` (AgentShield)** — roda no CI a cada PR; obrigatório para P5.
- **Continuous learning / instincts** — padrões recorrentes do projeto (money discipline, RLS, tradução §7) viram instintos persistentes entre sessões.
- **Verification loops** (`/loop-start`, pass@k) — para os fluxos fiscais críticos (emissão de nota, fechamento de folha) na fase de hardening.
- **Memória entre sessões (hooks)** — complementa o vault Obsidian; o vault continua fonte de verdade, hooks só re-priming.

❗ ECC **não substitui** os contratos do repo: `CLAUDE.md` continua sendo a constituição; em conflito, o repo vence.

---

## §4 — Identidade v2: "Arkan Claro" (Instrumento × Apple)

Direção aprovada pelo PO: **evoluir** Arkan mesclando com estética Apple — simples, fluido, bonito, compreensível à primeira vista, que se destaca. Não é rework: o tema é dirigido por tokens (`@theme`), então a v2 é uma **re-calibração**, e as funções/telas ficam.

**Tese nomeada:** *"O instrumento de precisão, agora leve na mão"* — mantém o DNA (precisão, UM verde, mono nos dados, confiança) e troca densidade técnica por clareza espacial.

| Mantém (DNA Arkan) | Recalibra (direção Apple) |
|---|---|
| UM acento verde = saúde fiscal | Mais respiro: escala de espaçamento ampliada, menos elementos por viewport |
| Mono tabular nos dados e valores | Serif Fraunces recua para momentos-marca (títulos de página, carimbo); UI text ganha hierarquia da sans (Hanken) com pesos generosos |
| Status cor+ícone+palavra, Carimbo como rito | Ornamento blueprint (crop marks, Fig., réguas decorativas) sai do caminho — vira assinatura rara, não moldura de todo painel |
| Radius pequeno, precisão | Radius levemente maior em superfícies grandes (continua longe de pílula); profundidade por camadas de material (blur/translucidez já existente no masthead), não sombra genérica |
| Motion com propósito | Motion fica MAIS protagonista: transições fluidas entre telas, springs suaves, contagem de números — fluidez é o "Apple feel" |
| Papel quente | Clarear 1 passo o papel; mais contraste de hierarquia por tamanho/peso, menos por fios — fios 1px só onde estruturam dados |

**Processo (Squad Experiência):** `[EXTRACT]` de 3 referências Apple-like (ex.: apple.com/br, Linear mobile, app de banco premium) → tokens v2 no `@theme` → passada nas 24 primitivas → gabarito (Notas) → demais lotes → brand pack (logo final, landing, social, e-mail, brand book). Gates anti-slop continuam valendo — "Apple" não é licença para virar genérico: a serifa, o verde único e o mono nos dados são inegociáveis.

> **Detalhamento PR-a-PR (auditoria UX × fases D0–D6 da v2):** `docs/plano-experiencia-ux-v2.md` — a sequência única de PRs do front, regida por «conteúdo antes da forma» (linguagem/dados/fluxo entram já; layout só depois dos tokens v2, para não pintar a mesma tela duas vezes).

---

## §5 — Mapa funcional (ferramenta a ferramenta: atual → alvo)

| Ferramenta | Hoje | Alvo production | Sprint |
|---|---|---|---|
| 01 Emissão NFS-e Nacional | ❌ | Emitir/cancelar/consultar via ADN, DANFSE em S3 | S2–S3 |
| 02 NF-e / captura | Focus OK | + classificação inteligente de entrada (CFOP/NCM via LLM + re-check) | S7 |
| 03 DAS / PGDAS-D | ✅ cálculo | + tabelas 2026, multa automática refletida em alertas | S2 |
| 04 Folha / pró-labore | ✅ cálculo | transmissão eSocial real (XML ICP-Brasil) | S4 |
| 05 Cadeia Reinf→DCTFWeb | 🟡 | orquestrada com freio humano antes de transmitir | S5 |
| 06 Contábil / relatórios | ✅ | + bloqueio mês encerrado no service, limite isento automático | S7 |
| 07 Conciliação / open finance | ✅ | webhook Pluggy → sync via Celery | S1 |
| 08 Agenda de obrigações | ✅ | urgência 3 níveis + tradução de siglas + push/WhatsApp | S2 |
| 09 Monitores de limite | ❌ | réguas R$81k/3,6M/4,8M com projeção; fluxo desenquadramento MEI→ME e sublimite | S7 |
| 10 Assistente IA | backend ✅ / front mock | ligado de verdade, onipresente, perguntas prontas contextuais | S6 |
| 11 Onboarding | wizard 5 passos | CNPJ-first (BrasilAPI pré-preenche), valor antes de formulário, persistente | S6 |
| 12 Certidões / compliance | 🟡 CND ok | CRF/CNDT reais via Celery | S7 |
| 13 Billing / assinatura | ❌ | gateway BR (Stripe ou Pagar.me), trial, planos, dunning | S8–S9 |
| 14 CBS/IBS 2027 | educacional | campos NT 2025.002 + cClassTrib atrás de feature flag | S10 |
| 15 Suporte / operação | ❌ | helpdesk, e-mail transacional, status page, runbooks | S9, S11 |

---

## §6 — As 12 sprints

**Marcos:** M1 (fim S2) fundação produção · M2 (fim S5) compliance ponta-a-ponta · M3 (fim S6) alpha interno completo · M4 (fim S9) **beta contadores no ar** · M5 (fim S11) beta validado + billing · M6 (fim S12) **lançamento público**.

### S1 — Fundação de produção (Plataforma + Qualidade)
Celery real (`celery[redis]`, workers + beat em produção), storage S3 (recibos, DANFSE, holerites), staging deploy sa-east-1, CI/CD (GitHub Actions: pytest+mypy+build+AgentShield), setup ECC (plugin + rules + hooks), webhook Pluggy→sync. **Front (paralelo):** UX PR1 — `lib/traducao/obrigacoes.ts` + `erros.ts` + apostos de tributos.
*DoD: deploy automatizado em staging; fila processando; zero sigla crua na agenda/home.*

### S2 — A guia do mês perfeita (Fiscal + Experiência)
Tabelas INSS/IRRF/FGTS 2026 via `/atualizar-aliquota` (issue #9, quando Portaria sair — senão mock + flag), alertas com multa automática LC 214/2025, UX PR2 (home = 3 respostas; urgência 3 níveis). Início NFS-e Nacional: credenciamento ADN + spike técnico da API.
*DoD: home responde "estou bem / o que pago / quanto" em 5s; urgência visível.* → **M1**

### S3 — NFS-e Nacional (Fiscal Core, sprint dupla-atenção)
Módulo `nfse_nacional`: emissão, cancelamento, consulta via ADN/emissor nacional; DANFSE; fallback municípios não migrados; golden tests por cenário (MEI serviço, SN com retenção ISS). **Experiência (paralelo):** `[EXTRACT]` + tokens v2 "Arkan Claro" + passada nas primitivas.
*DoD: nota de serviço autorizada em homologação ADN; showcase v2 aprovado no gate anti-slop.*

### S4 — eSocial de verdade (Fiscal + Plataforma)
Geração XML eSocial, assinatura ICP-Brasil (certificado A1 do cliente, armazenado cifrado — pgcrypto/KMS), envio + polling de recibos, tratamento de erros em PT humano. **Experiência:** gabarito Notas re-calibrado v2 + UX PR3 (cards mobile, ação primária por tela).
*DoD: admissão + folha transmitidas em produção restrita do eSocial.*

### S5 — Fechamento de mês ponta-a-ponta (Fiscal)
Orquestração eSocial(fechamento)→EFD-Reinf→DCTFWeb com freio humano (princípio: transmissão é ato consciente); tela "Fechar o mês" guiada — um botão, passos visíveis, Carimbo no fim. Telas v2 lotes A/C.
*DoD: E2E de mês completo numa empresa de teste: folha→eSocial→Reinf→DCTFWeb→DAS pago.* → **M2**

### S6 — Alpha interno (Experiência + Plataforma)
Assistente real no front (citação visível, perguntas prontas por tela), onboarding CNPJ-first com BrasilAPI + persistência, telas v2 lotes D/E, Carimbo como rito pós-ação em todos os fluxos. Dogfooding: rodar a empresa do próprio Lorenzo no sistema.
*DoD: onboarding <10 min sem ajuda; assistente respondendo com citação.* → **M3**

### S7 — Inteligência e limites (Fiscal + Experiência)
Monitores de limite com projeção (réguas 81k/3,6M/4,8M), fluxo desenquadramento MEI→ME e sublimite, monitor proativo de Fator R com simulação de pró-labore, classificação inteligente de NF de entrada, CRF/CNDT reais, bloqueio mês encerrado no service, limite isento automático.
*DoD: os 3 monitores ativos com dados reais; pendências conscientes #5, #6, #10 fechadas.*

### S8 — Hardening + marca (Qualidade + Experiência)
Pen-test RLS (tentativa cross-tenant automatizada), verification loops ECC nos fluxos críticos (pass@k), load test (k6: 500 empresas simuladas), backup/restore testado, rate limiting, LGPD (termos, privacidade, DPO, registro de tratamento). **Brand pack:** logo final, landing page, social, templates de e-mail, brand book v2.
*DoD: relatório de segurança sem crítico; landing no ar com waitlist.*

### S9 — Beta contadores (Qualidade + Plataforma)
Visão multi-empresa para o contador parceiro (lista de empresas, status consolidado), billing fase 1 (gateway BR, trial 30d, 2 planos), helpdesk + e-mail transacional (Resend/Postmark), docs de onboarding do contador, recrutar 5–10 contadores → 10–30 empresas.
*DoD: primeira empresa real de contador operando; cobrança de teste executada.* → **M4 — beta no ar**

### S10 — Iteração do beta + CBS/IBS (todas as squads)
Ciclo semanal: feedback do beta → correções priorizadas (SLA: bug fiscal = 48h). Sprint CBS/IBS: campos NT 2025.002 (vIBS, vCBS, cClassTrib, CST) nos emissores atrás de feature flag, golden tests, simulador atualizado com regras 2027.
*DoD: NPS dos contadores ≥8; nota com campos CBS/IBS válida em homologação.*

### S11 — Polish + self-service (Experiência + Plataforma)
Correções UX do beta, billing fase 2 (self-service completo, dunning, upgrade/downgrade), onboarding público sem contador, motion polish final (transições fluidas — o "Apple feel" em produção), Lighthouse ≥95 a11y/perf, dark mode validado por humano.
*DoD: P1–P9 do §1 todos verdes; beta ≥4 semanas sem incidente fiscal (P10 em curso).* → **M5**

### S12 — Lançamento público (todas as squads)
Status page, runbooks de incidente + simulação, on-call (alertas Grafana→celular), conteúdo de lançamento (a skill `analista-fiscal-market-research` alimenta o posicionamento), abertura do self-service, war room na primeira semana.
*DoD: P1–P10 TODOS verdes. Lançado.* → **M6** 🚀

---

## §7 — Riscos e mitigações

| Risco | Prob. | Mitigação |
|---|---|---|
| Credenciamento ADN/SERPRO/certificados demora (depende de terceiros) | Alta | Iniciar TODOS os credenciamentos na S1 (ação do PO); spike técnico antes da sprint de implementação |
| Portaria 2026 (tabelas INSS/IRRF) não sai a tempo | Média | Fluxo `/atualizar-aliquota` pronto; seed 2025 com banner de aviso; SCD permite corrigir retroativo |
| Identidade v2 derrapa para "genérico Apple-clone" | Média | Gates anti-slop continuam bloqueando merge; serifa+verde+mono inegociáveis; reviewer de contexto fresco |
| Erro fiscal em produção no beta | Média/grave | Beta via contadores (rede de segurança profissional), freio humano em toda transmissão, golden tests, SLA 48h |
| Escopo crescer (novas ideias no meio) | Alta | Regra do Plano: out-of-scope é declarado; ideias novas entram no backlog pós-M6, não na sprint |
| ECC conflitar com convenções do repo | Baixa | Instalação seletiva; `CLAUDE.md` vence em conflito; hooks com perfil `minimal` primeiro |

---

## §8 — Governança e rituais

- **Cadência:** sprint de 2 semanas; `/multi-plan` na abertura, review + `/quality-gate` + reviewer fresco em todo PR; fechamento atualiza `log_agente.md` (backend), `HANDOFF.md` (frontend) e `docs/roadmap.md` (write-back obrigatório, sem pedir confirmação).
- **Definition of Done universal:** pytest + mypy verdes · golden test em todo cálculo novo · AgentShield sem crítico · gate UX (5s/sigla/ação/urgência/375px) em toda tela tocada · vault Obsidian sincronizado.
- **Freios humanos (nunca automatizar):** transmissão ao governo, alteração de tabela tributária, deploy em produção, cobrança.
- **Métricas de acompanhamento:** burn das sprints vs marcos M1–M6; contagem de testes (nunca cai); empresas ativas no beta; tempo de onboarding; incidentes fiscais (alvo: zero).

---

## §9 — Primeiras ações (semana 1)

1. **PO:** iniciar credenciamentos (ADN/emissor nacional, SERPRO produção, gateway de billing, domínio/e-mail da marca) — caminho crítico externo.
2. **Orquestrador:** instalar ECC (plugin seletivo) + criar agentes novos (`platform-dev`, `e2e-tester`, `docs-keeper`) em `.claude/agents/`.
3. **Squad Plataforma:** começar S1 (Celery + S3 + CI/CD + staging).
4. **Squad Experiência:** começar UX PR1 (tradução) — zero dependência externa, ganho imediato.
5. **Atualizar `CLAUDE.md`** com referência a este plano como fonte de verdade do workstream production-ready.
