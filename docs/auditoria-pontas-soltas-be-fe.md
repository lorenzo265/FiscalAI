# Auditoria — Pontas soltas Backend ↔ Frontend

**Data:** 2026-06-22 · **Autor:** orquestrador (auditoria multi-agente, 12 subagentes) · **Gatilho:** "campos não conectados entre BE e FE (ex.: dark mode), pontas soltas não aproveitadas".

> **Propósito:** separar o que está **em desenvolvimento/planejado** (M3, M4, roadmap de ondas — não mexer) do que é **ponta solta real** (capacidade construída sem dono no roadmap, ou bug). NÃO é ordem de implementação — é mapa de decisão para uma onda futura.

---

## 0. Método e estado base (o quadro mudou)

Varredura cruzada: 36 routers do backend (`app/modules/*/router.py` + `main.py`) × ~45 rotas do frontend (`src/app/**/page.tsx`) × camada de dados × inventário de controles de UI.

**Correção de premissa:** o frontend **não é mais mock-only**. Está **real-backend-first** (Ondas 1–4):
- Cliente HTTP real em `src/lib/http.ts` (`fetchJson` → `http://localhost:8000/v1` via `NEXT_PUBLIC_API_BASE_URL`).
- **JWT real** em `localStorage` (`arkan:token` / `arkan:token-exp` / `arkan:email`); 401 → `limparSessao()` + `/login`.
- **11 domínios** com adapters em `src/lib/api/*` (auth, empresa, fiscal, agenda, notas, pessoal, controles, contabil, compliance, assistente, relatorios).
- Dexie/IndexedDB virou **camada de suporte/fallback honesto** (drafts, catálogo, lookup) — não fonte de verdade fiscal.

As pontas soltas são, portanto, **pontuais e concentradas** — não um abismo total.

---

## 1. Correção factual: o **dark mode não está quebrado**

O subagente de controles errou ao reportar "preso no modo claro". Verificado em `analista-fiscal-web/src/app/globals.css` (~linhas 167–229):

- Existe `@media (prefers-color-scheme: dark) { :root:not(.light) { … } }` que **re-deriva todos os tokens automaticamente**. **Se o SO está no escuro, o app já renderiza escuro sozinho.**
- A classe `.dark` é descrita no próprio CSS como *"gancho para um futuro toggle"*.
- Identidade é **"Arkan Claro"** (light-first por marca); `PLANO_PRODUCTION_READY` agenda "dark mode validado por humano" para **S11**.

**Veredito:** o toggle manual ausente é **item de roadmap (S11), não erro.** Falso positivo.

---

## 2. EM DESENVOLVIMENTO / PLANEJADO — não mexer

M3 e M4 são **100% backend/infra**; nenhuma tela órfã depende deles. Outras pontas da auditoria já têm dono no roadmap:

| Item | Onde já está coberto |
|---|---|
| LGPD `/exportar` + `/excluir`, AES-256 PII, refresh token JWT, security headers, CI gates (Semgrep) | **M3 em curso** — branch `feat/m3-lgpd-seguranca`; 6.1 (security headers) feito; 6.2–6.5 a fazer |
| Storage S3 efetivo, transmissão EFD-Reinf→SERPRO, eSocial real (flip de flag), NFS-e ADN, e-mail transacional, Dockerfile/`error.tsx`/retry do front, IaC | **M4** (planejado, não iniciado) |
| Tela `/assinatura` (billing) | M2 §5 + **S8–S9** (backend `app/modules/billing` já existe) |
| **Certificado A1** por empresa, cifrado (pgcrypto/KMS) | **S4** (a tela FE de upload já existe esperando o backend) |
| "Fechar o mês" guiado + encerramento contábil | **X14 / S5** (casado com a cadeia eSocial→Reinf→DCTFWeb) |
| Certidões CRF/CNDT reais | **S7** (hoje CND via SERPRO; CRF/CNDT placeholder) |
| Cancelamento de NFS-e (via ADN/emissor nacional) | **S3–S4** |
| Assistente real / Onboarding CNPJ-first | **X16 / X15 — já feitos** |
| Dark mode (toggle manual + validação) | **S11** (auto por SO já funciona) |
| Tabelas INSS/IRRF/FGTS 2026 | issue #9 (aguarda Portaria MPS/MF) |

> O roadmap do frontend (`docs/plano-experiencia-ux-v2.md`, PRs **X1–X19**) é **exclusivamente re-skin + UX de telas existentes** (tradução, urgência, tokens v2, número-herói, motion). **Não inclui** criar telas para módulos novos — daí o vão da §3.2.

---

## 3. PONTAS SOLTAS REAIS (fora de todo plano)

### 3.1 Bug claro
- **🔴 Logout morto.** Auth é JWT real e a função `limparSessao()`/`sair()` **existe** em `src/lib/api/auth.ts`, mas o item "Sair" em `src/components/layout/topbar.tsx` (~linha 161) não tem `onClick`. **Não há como sair do app.** Itens "Perfil" e "Preferências" do mesmo menu também sem handler. → *chip de tarefa criado (`task_99d964d0`).*

### 3.2 Backend pronto e testado, sem tela **e sem tela planejada** (capacidade desperdiçada)

| Módulo backend | Endpoints | O que está parado |
|---|---|---|
| **advisor** | 8 | Anomalias, sugestões (Fator R), digest semanal — o "cérebro" do produto, invisível |
| **conciliação Match** (NF×banco) | 4 | Algoritmo + confirmar/rejeitar prontos; nenhuma tela |
| **icms** | 2 | Apuração ICMS mensal — zero UI |
| **declaração anual** (DEFIS/DASN) | 4 | Geração + transmissão SERPRO — invisível |
| **det** (caixa trabalhista) | 3 | Classificação LLM pronta; `compliance/intimacoes` usa seed dummy em vez disso |
| **imobilizado** | 6 | CRUD + depreciação linear automática |
| **provisões** | 2 | Férias/13º/INSS/FGTS — só aparecem embutidos no DRE |
| **sócios/pró-labore/distribuição** | ~5 | Cálculo INSS/IRRF + limites de presunção prontos |
| **reinf** (retenções PJ→PJ) | 2 | IR 1,5% + CSRF 4,65% prontos |
| **multa/juros** | 2 | Só "refletido em alertas" foi planejado (S2); o simulador não tem tela |
| **marketplace** | 15 | Só citado no Assistente; sem fluxo de consulta/parceiros/pagamento |
| **migração** (SPED/CSV histórico) | 8 | Import de legado; runbook existe, tela não |
| **tabelas-admin** (SCD alíquotas) | 18 | Painel de ops (não usuário final) |

### 3.3 Telas em mock com backend **pronto**, sem tarefa registrada (quick wins de fiação)
- **Reforma CBS/IBS** — backend tem 4 endpoints de simulação **reais** (`/reforma/simulacao`, `/aliquota-vigente`, `/fase-atual`), mas a tela `/fiscal/reforma-tributaria` é placeholder estático. *(O plano trata CBS/IBS como "só educacional" até S10 — o placeholder não viola o plano, mas desperdiça os endpoints prontos.)*
- **PUT empresa** — `PUT /v1/empresas/{id}` existe; `form-empresa` só grava no contexto (perde no reload).
- **e-CAC** — `POST /e-cac/sync` + `GET /e-cac/mensagens` prontos; `intimacoes` usa seed local.
- **Monitor cadastral** — painel hardcoda `cnpjAtivo=true` em vez de ler `GET /monitor/rfb/atual`.

### 3.4 Telas em mock **sem backend e sem plano de backend**
- **🔴 Manifesto de entrada de NF-e** — obrigação legal (180 dias); botão existe e é ilusório; **não aparece em nenhum plano**.
- **Convite de usuários** — mock (`setTimeout` + toast fake); gestão multi-usuário não claramente escopada (talvez "visão do contador", S9).

---

## 4. Veredito

O grande vazamento **não** é o dark mode (falso positivo) nem o M3/M4 (em curso, saudáveis). É um **descompasso entre os dois roadmaps**:

- o **backend** foi até a Sprint 22 e construiu ~36 módulos;
- o **frontend** fez um re-skin (Arkan v2) de ~40 telas existentes e ligou 11 domínios — mas o re-skin **nunca teve a missão de criar telas para os módulos novos**.

Resultado: ~10–13 módulos de backend prontos e testados (§3.2) caíram no vão entre os planos, mais o **logout morto** (§3.1) e o **manifesto de NF-e** (§3.4) que são lacunas legais/funcionais reais.

### Sugestão de priorização para uma onda futura (quando o PO quiser)
1. **Logout** (minutos; bug) — chip já criado.
2. **Quick wins de fiação** (§3.3): PUT empresa, e-CAC, monitor cadastral, Reforma — backend já pronto, baixo custo.
3. **Telas de módulos órfãos por valor de negócio** (§3.2): advisor (diferencial do produto) → conciliação Match → icms/declaração anual → demais.
4. **Manifesto de NF-e** (§3.4) — precisa endpoint novo no backend; obrigação legal.

> **Não autoriza implementação.** M3/M4 e o roadmap de ondas seguem intactos. Este doc é insumo de decisão.
