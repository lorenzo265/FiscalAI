# Plano de Implementação Frontend — Analista Fiscal

> **Documento auto-contido. O Claude Code deve conseguir executar este plano do zero, sem precisar de outras referências, e ao final entregar um protótipo navegável que demonstra a visão completa do produto.**
>
> **Versão:** 1.0
> **Última atualização:** 2026-05-08
> **Escopo:** SOMENTE frontend. Zero backend. Tudo mockado com persistência local.
> **Identidade visual:** Dark theme do `fiscalai_v4.html` (lime + blue + amber).
> **Profundidade:** Full mock — leitura + escrita simulada com persistência via IndexedDB.

---

## 0. Como ler este documento

1. **Leia inteiro antes de começar.** Não pule pras fases.
2. **Não invente decisões.** Se algo não estiver aqui, pare e pergunte.
3. **Não substitua tecnologias.** O stack está cravado por decisões que dependem umas das outras.
4. **Cada fase tem critério de aceitação binário.** Só avance quando todos passarem.
5. **Obediência > criatividade.** Este plano foi feito pra ser executado, não reinterpretado.

---

## 1. Visão do produto (5 minutos)

**O que é:** SaaS que substitui o serviço contábil tradicional para PMEs brasileiras. Faturamento alvo R$200k–R$50M/ano, em Simples Nacional ou Lucro Presumido.

**Promessa:** *"Você sabe o que está acontecendo no seu fiscal — sem precisar ser contador."*

**Persona:** dono de PME. Pode ser dono de restaurante que estudou até o ensino médio. Não é contador. Não vai aprender a ser contador.

**As 5 leis de UX (invioláveis):**

1. **Nunca mostrar códigos fiscais ao usuário.** CFOP, CST, NCM, Anexo são invisíveis. Traduzir em linguagem humana.
2. **Status sobre números.** "Seus impostos estão normais esse mês" antes de "PIS R$3.847,22".
3. **Uma ação por alerta.** Todo problema vem com um botão de solução.
4. **Dashboard é health report, não control panel.** Usuários leem, não operam.
5. **3 camadas por tela:** Headline (uma métrica) → Signal (2–4 cards) → Detail (collapsed por padrão).

**Teste de cada tela:** *"Um dono de restaurante que estudou até o ensino médio entende isso em 5 segundos?"* Se não, redesenha.

---

## 2. Stack final (cravado)

### 2.1 Versões exatas

| Camada | Tecnologia | Versão | Decisão |
|---|---|---|---|
| Framework | Next.js | `15.x` (App Router) | Cravado. SSR/RSC quando backend chegar. Route Handlers como fake-API. |
| Runtime | React | `19.x` | Cravado. Necessário pra Next 15. |
| Linguagem | TypeScript | `5.6+` | Strict mode. `"strict": true`, `"noUncheckedIndexedAccess": true`. |
| Estilo | Tailwind CSS | `v4` (zero-config) | Cravado. v4 simplifica setup, sem `tailwind.config`. |
| Components | shadcn/ui | canary (Tailwind v4 compatible) | Cravado. Vamos customizar pesadamente os tokens. |
| Server state | TanStack Query | `v5` | Cravado. Mesmo com mock, simula caching real. |
| Tabelas | TanStack Table | `v8` | Cravado. Listagens fiscais exigem sort/filter sério. |
| Client state | Zustand | `v5` | Cravado. Sidebar, filtros locais, wizards. |
| Forms | React Hook Form | `v7` | Cravado. |
| Validação | Zod | `v3` | Cravado. Schemas compartilhados entre form, route handler e tipos. |
| Charts | Recharts | `v2` | Cravado. Customizado com paleta dark. |
| Datas | date-fns + date-fns-tz | `v4` | Cravado. Fuso BR não-negociável. |
| Ícones | Lucide React | latest | Cravado. Vem com shadcn. |
| Persistência local | Dexie | `v4` | Cravado. IndexedDB pra full mock. |
| Geração de dados | @faker-js/faker | `v9` | Dev only. Seeds realistas. |
| Geração PDF | jsPDF | latest | Pra mock de DAS, holerite, boleto. |
| Código de barras | jsbarcode | latest | Pra DAS/boleto mock. |
| QR Code | qrcode | latest | Pra PIX mock. |
| Toasts | sonner | latest | Mais elegante que shadcn toast default. |
| Drawer mobile | vaul | latest | Já vem no shadcn. |
| Command palette | cmdk | latest | Já vem no shadcn. |
| URL state | nuqs | latest | Filtros como search params type-safe. |
| Animação | framer-motion | `v11` | Pra transições de página, modais, listas. |
| Lint | ESLint + Prettier | flat config | Cravado. Sem custom rules além do `next/core-web-vitals`. |

### 2.2 O que NÃO usar (anti-padrões)

- ❌ **MSW (Mock Service Worker).** Vamos usar Route Handlers + Dexie. MSW seria uma terceira camada que precisa ser removida quando o backend chegar.
- ❌ **next-themes.** Tema é fixo dark. Sem toggle.
- ❌ **Redux / Redux Toolkit.** Zustand basta.
- ❌ **Material UI / Ant Design / Chakra.** shadcn customizado.
- ❌ **Tremor.** Recharts é suficiente. Tremor adiciona dependência sem grande ganho.
- ❌ **Server Actions pra mock.** Use Route Handlers. Server Actions misturam camadas e dificultam migração.
- ❌ **`any` em TypeScript.** Sob nenhuma hipótese.
- ❌ **Inline styles.** Use Tailwind ou CSS modules.

### 2.3 Convenções de código

```
File naming:        kebab-case.tsx              (ex: apuracao-card.tsx)
Component naming:   PascalCase                   (ex: ApuracaoCard)
Hook naming:        useCamelCase                 (ex: useApuracaoAtual)
Route paths:        /portuguese-natural          (ex: /fiscal/apuracao, /pessoal/folha)
Types:              PascalCase + sufixo de domínio (ex: ApuracaoFiscal, NotaFiscalSaida)
Zod schemas:        camelCaseSchema              (ex: apuracaoFiscalSchema)
Constants:          SCREAMING_SNAKE_CASE         (ex: REGIMES_TRIBUTARIOS)
```

- Server components por padrão. `"use client"` somente onde precisar de interatividade.
- Cada componente em arquivo próprio. Zero "default export" — sempre named exports.
- Imports absolutos via `@/` (configurado no `tsconfig.json`).
- Componentes do domínio fiscal em `src/components/<modulo>/`. Primitives em `src/components/ui/`.

---

## 3. Arquitetura de Mock — a parte que define o projeto

Esta seção é a mais importante. Ler com atenção.

### 3.1 O problema

O projeto vai ter backend (FastAPI + Postgres) algum dia. Mas hoje é só frontend. Precisamos de uma estratégia de mock que:

1. Persista dados entre reloads (senão "emitir NF" vira mentira).
2. Simule comportamento de API real (latência, erros, paginação).
3. Permita migração trivial pro backend real, sem reescrever componentes.
4. Seja type-safe end-to-end.

### 3.2 A solução: 4 camadas

```
┌─────────────────────────────────────────────────────────┐
│  Camada 4: Componentes React                           │
│  Usa hooks do TanStack Query (useApuracaoAtual, etc.)  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Camada 3: API Client                                   │
│  src/lib/api-client.ts                                  │
│  - Funções tipadas: api.fiscal.getApuracaoAtual()      │
│  - Faz fetch pros Route Handlers                        │
│  - Único ponto de troca quando backend real chegar      │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Camada 2: Route Handlers (Next.js)                     │
│  src/app/api/mock/.../route.ts                          │
│  - Simula latência (await sleep(150-400ms))             │
│  - Pode simular erros (random 2% de 500)                │
│  - Lê de seeds estáticas E delega escritas pro client   │
│  - Retorna dados validados pelo Zod                     │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
┌──────────────────────┐  ┌─────────────────────────────┐
│  Camada 1a: Seeds    │  │  Camada 1b: Dexie           │
│  src/lib/mocks/      │  │  src/lib/db/                │
│  Dados imutáveis     │  │  IndexedDB (CLIENT-SIDE)    │
│  - tabelas IBGE      │  │  - empresa cadastrada       │
│  - alíquotas         │  │  - NFs emitidas             │
│  - calendário fiscal │  │  - lançamentos              │
│  - municípios        │  │  - funcionários             │
└──────────────────────┘  │  - tudo que o usuário cria  │
                          └─────────────────────────────┘
```

### 3.3 Detalhe importante: Route Handler ≠ Dexie

Route Handlers rodam no Node (server). Dexie é IndexedDB (browser). **Eles não se comunicam diretamente.**

Estratégia:

- **Dados imutáveis (READ-ONLY)** → ficam em seeds estáticos no `src/lib/mocks/`, lidos pelo Route Handler. Ex: tabela de alíquotas do Simples, lista de municípios, prazos do calendário fiscal.
- **Dados mutáveis (CRUD do usuário)** → ficam no Dexie (client-side). O Route Handler não os enxerga. Mas a **API Client** abstrai essa diferença. Quando o componente chama `api.notas.listar()`, o api-client decide internamente:
  - Se o endpoint é "read-only de seed" → faz fetch pro Route Handler.
  - Se é "CRUD de usuário" → vai direto no Dexie.

### 3.4 Por que essa arquitetura migra fácil pro backend real

Quando o FastAPI ficar pronto:

1. **Seeds estáticos** → o Route Handler vira proxy: `fetch(BACKEND_URL + path)`.
2. **Dexie** → trocamos por chamadas ao mesmo Route Handler-proxy. O Dexie morre.
3. **Componentes** → não muda **nada**. Eles só usam os hooks.

Esse desenho é o mesmo padrão BFF (Backend For Frontend) que vai existir em produção.

### 3.5 Padrão de Route Handler

Todo Route Handler segue:

```typescript
// src/app/api/mock/fiscal/apuracao/atual/route.ts
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { mockLatency, mockMaybeError } from "@/lib/mocks/utils";
import { apuracaoFiscalSchema } from "@/lib/schemas/fiscal";
import { gerarApuracaoMock } from "@/lib/mocks/fiscal";

export async function GET(req: NextRequest) {
  await mockLatency(); // 150–400ms aleatório
  mockMaybeError(0.02); // 2% chance de 500 (testar error states)

  const cnpj = req.nextUrl.searchParams.get("cnpj");
  if (!cnpj) {
    return NextResponse.json(
      { error: "cnpj_required" },
      { status: 400 }
    );
  }

  const data = gerarApuracaoMock(cnpj);
  const parsed = apuracaoFiscalSchema.safeParse(data);

  if (!parsed.success) {
    console.error("Mock data invalid:", parsed.error);
    return NextResponse.json({ error: "invalid_mock" }, { status: 500 });
  }

  return NextResponse.json(parsed.data);
}
```

### 3.6 Padrão de API Client

```typescript
// src/lib/api-client.ts
import { apuracaoFiscalSchema, type ApuracaoFiscal } from "@/lib/schemas/fiscal";
import { db } from "@/lib/db";

const BASE = "/api/mock";

async function fetchJson<T>(path: string, schema: z.ZodSchema<T>): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return schema.parse(await res.json());
}

export const api = {
  fiscal: {
    // SEED-BACKED (Route Handler)
    getApuracaoAtual: (cnpj: string) =>
      fetchJson(`/fiscal/apuracao/atual?cnpj=${cnpj}`, apuracaoFiscalSchema),

    // ... outros
  },

  notas: {
    // DEXIE-BACKED (CRUD do usuário, vai direto no IndexedDB)
    async listar(filtros: FiltrosNF) {
      return db.notasFiscais
        .where("emissao")
        .between(filtros.inicio, filtros.fim)
        .toArray();
    },

    async emitir(nf: NotaFiscalInput) {
      const completa = preencherNFMock(nf); // calcula impostos, gera chave, etc.
      await db.notasFiscais.add(completa);
      return completa;
    },
  },
};
```

### 3.7 Padrão de hook (TanStack Query)

```typescript
// src/hooks/use-apuracao-atual.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useEmpresaAtual } from "@/hooks/use-empresa-atual";

export function useApuracaoAtual() {
  const { cnpj } = useEmpresaAtual();
  return useQuery({
    queryKey: ["fiscal", "apuracao-atual", cnpj],
    queryFn: () => api.fiscal.getApuracaoAtual(cnpj),
    enabled: !!cnpj,
    staleTime: 60_000,
  });
}
```

### 3.8 Inicialização do Dexie e seed da empresa demo

No primeiro load, se Dexie estiver vazio, semear com:
- 1 empresa demo "FiscalAI Demo Ltda" (CNPJ fictício, Simples Nacional, Anexo III, RS)
- 6 meses de NFs sintéticas (~30 emitidas, ~80 recebidas)
- 12 lançamentos contábeis sintéticos
- 2 funcionários demo
- Conta bancária demo com 60 transações

Isso é feito em `src/lib/db/seed.ts`, chamado uma única vez no `EmpresaProvider`.

---

## 4. Estrutura de pastas

```
analista-fiscal-web/
├── package.json
├── tsconfig.json
├── next.config.mjs
├── postcss.config.mjs
├── components.json              ← config do shadcn
├── .eslintrc.json
├── .prettierrc
├── .gitignore
├── .env.local.example
│
├── public/
│   ├── favicon.ico
│   ├── logo.svg
│   └── bancos/                  ← logos SVG mock
│       ├── itau.svg
│       ├── bradesco.svg
│       ├── nubank.svg
│       └── bb.svg
│
└── src/
    ├── app/
    │   ├── layout.tsx           ← root layout, providers globais
    │   ├── page.tsx             ← redirect: /onboarding ou /home
    │   ├── globals.css          ← design tokens fiscalai_v4
    │   │
    │   ├── (auth)/
    │   │   ├── layout.tsx
    │   │   ├── login/page.tsx
    │   │   └── onboarding/
    │   │       ├── page.tsx
    │   │       └── components/   ← passos do wizard
    │   │
    │   ├── (dashboard)/
    │   │   ├── layout.tsx       ← shell (sidebar + topbar + alertas)
    │   │   ├── home/page.tsx
    │   │   │
    │   │   ├── fiscal/
    │   │   │   ├── page.tsx
    │   │   │   ├── apuracao/
    │   │   │   │   ├── page.tsx
    │   │   │   │   └── [ano]/[mes]/page.tsx
    │   │   │   ├── guias/page.tsx
    │   │   │   ├── simulador/page.tsx
    │   │   │   └── reforma-tributaria/page.tsx
    │   │   │
    │   │   ├── notas/
    │   │   │   ├── page.tsx
    │   │   │   ├── entrada/page.tsx
    │   │   │   ├── saida/
    │   │   │   │   ├── page.tsx
    │   │   │   │   └── nova/page.tsx
    │   │   │   └── [chave]/page.tsx
    │   │   │
    │   │   ├── contabil/
    │   │   │   ├── page.tsx          ← balancete
    │   │   │   ├── lancamentos/page.tsx
    │   │   │   ├── razao/[conta]/page.tsx
    │   │   │   └── encerramento/page.tsx
    │   │   │
    │   │   ├── controles/
    │   │   │   ├── page.tsx          ← fluxo de caixa
    │   │   │   ├── pagar/page.tsx
    │   │   │   ├── receber/page.tsx
    │   │   │   ├── ativos/page.tsx
    │   │   │   └── bancos/
    │   │   │       ├── page.tsx
    │   │   │       └── conectar/page.tsx ← Open Finance mock
    │   │   │
    │   │   ├── pessoal/
    │   │   │   ├── page.tsx          ← resumo da folha
    │   │   │   ├── funcionarios/
    │   │   │   │   ├── page.tsx
    │   │   │   │   ├── novo/page.tsx
    │   │   │   │   └── [id]/page.tsx
    │   │   │   ├── folha/[ano]/[mes]/page.tsx
    │   │   │   └── esocial/page.tsx
    │   │   │
    │   │   ├── relatorios/
    │   │   │   ├── dre/page.tsx
    │   │   │   ├── balanco/page.tsx
    │   │   │   ├── dfc/page.tsx
    │   │   │   └── indicadores/page.tsx
    │   │   │
    │   │   ├── compliance/
    │   │   │   ├── page.tsx
    │   │   │   ├── certidoes/page.tsx
    │   │   │   ├── intimacoes/page.tsx
    │   │   │   └── parcelamentos/page.tsx
    │   │   │
    │   │   ├── agenda/page.tsx
    │   │   ├── assistente/page.tsx
    │   │   │
    │   │   └── configuracoes/
    │   │       ├── page.tsx
    │   │       ├── empresa/page.tsx
    │   │       ├── certificado/page.tsx
    │   │       ├── integracoes/page.tsx
    │   │       └── usuarios/page.tsx
    │   │
    │   └── api/
    │       └── mock/             ← TODA fake-API aqui
    │           ├── fiscal/
    │           ├── notas/
    │           ├── contabil/
    │           ├── compliance/
    │           ├── agenda/
    │           ├── empresa/
    │           ├── openfinance/
    │           ├── assistente/
    │           └── reforma/
    │
    ├── components/
    │   ├── ui/                   ← shadcn customizado
    │   ├── layout/
    │   │   ├── sidebar.tsx
    │   │   ├── topbar.tsx
    │   │   ├── alertas-flutuantes.tsx
    │   │   └── empresa-switcher.tsx
    │   │
    │   ├── fiscal/
    │   │   ├── fiscal-health-score.tsx
    │   │   ├── apuracao-card.tsx
    │   │   ├── guia-pagamento.tsx
    │   │   ├── simulador-regime.tsx
    │   │   └── reforma-impacto.tsx
    │   │
    │   ├── notas/
    │   │   ├── lista-notas.tsx
    │   │   ├── emissor-nf.tsx
    │   │   └── danfe-mock.tsx
    │   │
    │   ├── contabil/
    │   │   ├── balancete.tsx
    │   │   ├── livro-diario.tsx
    │   │   └── razao.tsx
    │   │
    │   ├── controles/
    │   │   ├── fluxo-caixa.tsx
    │   │   ├── conta-bancaria-card.tsx
    │   │   └── conectar-banco-modal.tsx
    │   │
    │   ├── pessoal/
    │   │   ├── holerite-mock.tsx
    │   │   └── ficha-funcionario.tsx
    │   │
    │   ├── relatorios/
    │   │   ├── dre-render.tsx
    │   │   └── balanco-render.tsx
    │   │
    │   ├── compliance/
    │   │   └── ...
    │   │
    │   ├── assistente/
    │   │   ├── chat-sidebar.tsx
    │   │   └── mensagem-bubble.tsx
    │   │
    │   ├── onboarding/
    │   │   ├── passo-cnpj.tsx
    │   │   ├── passo-regime.tsx
    │   │   ├── passo-certificado.tsx
    │   │   ├── passo-bancos.tsx
    │   │   └── passo-conclusao.tsx
    │   │
    │   └── shared/
    │       ├── empty-state.tsx
    │       ├── loading-state.tsx
    │       ├── error-state.tsx
    │       ├── moeda.tsx          ← formata BRL
    │       ├── data-br.tsx        ← formata data BR
    │       ├── pill.tsx           ← chip de status
    │       └── stat-card.tsx
    │
    ├── hooks/
    │   ├── use-empresa-atual.ts
    │   ├── use-apuracao-atual.ts
    │   ├── ... (1 por entidade do domínio)
    │
    ├── lib/
    │   ├── api-client.ts
    │   ├── query-client.ts
    │   │
    │   ├── db/
    │   │   ├── index.ts          ← Dexie instance
    │   │   ├── schema.ts          ← tabelas e índices
    │   │   └── seed.ts           ← seed inicial
    │   │
    │   ├── mocks/
    │   │   ├── utils.ts          ← latency, error, faker setup
    │   │   ├── seeds/
    │   │   │   ├── municipios.ts
    │   │   │   ├── ncm.ts
    │   │   │   ├── cfop.ts
    │   │   │   ├── aliquotas-simples.ts
    │   │   │   ├── prazos-fiscais.ts
    │   │   │   └── bancos-openfinance.ts
    │   │   ├── fiscal.ts         ← geradores: apuração, guias
    │   │   ├── notas.ts          ← gerador NF mock
    │   │   ├── compliance.ts
    │   │   ├── reforma.ts
    │   │   └── assistente.ts
    │   │
    │   ├── schemas/              ← Zod, fonte da verdade
    │   │   ├── empresa.ts
    │   │   ├── fiscal.ts
    │   │   ├── notas.ts
    │   │   ├── contabil.ts
    │   │   ├── controles.ts
    │   │   ├── pessoal.ts
    │   │   ├── compliance.ts
    │   │   └── assistente.ts
    │   │
    │   ├── pdf/                  ← geradores de PDF mock
    │   │   ├── das.ts
    │   │   ├── danfe.ts
    │   │   ├── holerite.ts
    │   │   └── boleto.ts
    │   │
    │   ├── format/
    │   │   ├── moeda.ts          ← BRL formatter
    │   │   ├── cnpj.ts           ← formata e valida
    │   │   ├── cpf.ts
    │   │   ├── data.ts           ← formata data BR
    │   │   └── numero.ts
    │   │
    │   ├── fiscal/
    │   │   ├── calcula-das.ts    ← cálculo Simples Nacional mock
    │   │   ├── calcula-fator-r.ts
    │   │   └── ...
    │   │
    │   └── stores/                ← Zustand
    │       ├── ui-store.ts        ← sidebar, modais
    │       └── filtros-store.ts   ← filtros globais
    │
    ├── styles/
    │   └── tokens.css             ← variáveis fiscalai_v4
    │
    └── types/
        └── domain.ts              ← types globais inferidos dos schemas
```

---

## 5. Design system

### 5.1 Design tokens — `src/app/globals.css`

Copiar exatamente do `fiscalai_v4.html`:

```css
@import "tailwindcss";

@theme {
  /* fontes */
  --font-sans: "Plus Jakarta Sans", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", monospace;

  /* paleta — copiada do fiscalai_v4.html */
  --color-bg: #06080f;
  --color-bg-2: #0c0f1a;
  --color-card: #111624;
  --color-card-2: #161c2e;
  --color-card-3: #1c2338;

  --color-line: rgba(255, 255, 255, 0.06);
  --color-line-2: rgba(255, 255, 255, 0.11);

  --color-lime: #a3ff6b;
  --color-lime-d: rgba(163, 255, 107, 0.12);
  --color-blue: #4d8eff;
  --color-blue-d: rgba(77, 142, 255, 0.12);
  --color-amber: #ffb84d;
  --color-amber-d: rgba(255, 184, 77, 0.12);
  --color-red: #ff5566;
  --color-red-d: rgba(255, 85, 102, 0.12);

  --color-txt: #dde3f0;
  --color-txt-2: #8892a8;
  --color-txt-3: #4a5268;

  /* shape */
  --radius-md: 10px;
  --radius-sm: 6px;

  /* transition */
  --ease-default: cubic-bezier(0.4, 0, 0.2, 1);
}

@layer base {
  html {
    font-family: var(--font-sans);
    background: var(--color-bg);
    color: var(--color-txt);
    -webkit-font-smoothing: antialiased;
  }

  /* grid pattern de fundo, igual fiscalai_v4 */
  body {
    background-image:
      linear-gradient(rgba(163, 255, 107, 0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(163, 255, 107, 0.025) 1px, transparent 1px);
    background-size: 48px 48px;
    min-height: 100vh;
  }

  /* números fiscais SEMPRE em mono */
  .num,
  .mono {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }
}
```

### 5.2 Fontes — carregar no root layout

```tsx
// src/app/layout.tsx
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";

const sans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-sans-loaded",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
  variable: "--font-mono-loaded",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${sans.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

### 5.3 Primitives shadcn a customizar

Quando rodar `npx shadcn add <component>`, **abrir o arquivo gerado em `components/ui/` e substituir as classes** pra usar nossos tokens. Lista mínima:

- `button` (variants: `default` lime, `secondary` blue, `ghost`, `outline`, `destructive` red)
- `input`
- `label`
- `card`
- `dialog`
- `drawer`
- `dropdown-menu`
- `select`
- `tabs`
- `badge`
- `tooltip`
- `popover`
- `command` (palette)
- `sonner` (toasts)
- `sheet`
- `accordion`
- `alert`
- `skeleton`
- `separator`
- `switch`
- `checkbox`
- `radio-group`
- `progress`
- `scroll-area`
- `table` (vamos usar com TanStack Table)

### 5.4 Componentes do domínio (criar do zero)

#### `Moeda`
```tsx
// src/components/shared/moeda.tsx
type Props = { valor: number; className?: string };
export function Moeda({ valor, className }: Props) {
  const fmt = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
  return <span className={`mono ${className ?? ""}`}>{fmt.format(valor)}</span>;
}
```

#### `Pill` — chip de status
```tsx
// src/components/shared/pill.tsx
type Tom = "ok" | "warn" | "error" | "info" | "neutral";
type Props = { tom: Tom; children: React.ReactNode };

const tons: Record<Tom, string> = {
  ok: "bg-lime/12 text-lime border-lime/22",
  warn: "bg-amber/12 text-amber border-amber/22",
  error: "bg-red/12 text-red border-red/22",
  info: "bg-blue/12 text-blue border-blue/22",
  neutral: "bg-card-2 text-txt-2 border-line-2",
};

export function Pill({ tom, children }: Props) {
  return (
    <span
      className={`mono inline-block text-[9px] px-2 py-0.5 rounded-full tracking-wider font-bold border ${tons[tom]}`}
    >
      {children}
    </span>
  );
}
```

#### `StatCard`
```tsx
type Props = { label: string; valor: string; tom?: Tom; sub?: string };
// renderiza igual ao .stat do fiscalai_v4
```

#### `EmptyState`, `LoadingState`, `ErrorState`
Componentes obrigatórios em toda lista. Sempre.

---

## 6. Roteamento — todas as rotas

### 6.1 Rotas públicas
```
/login                           ← form mock (qualquer email/senha funciona)
/onboarding                      ← wizard 5 passos
```

### 6.2 Rotas autenticadas (dashboard)
```
/home                            ← Fiscal Health Score + alertas + 3 atalhos

/fiscal                          ← Apuração do mês atual (DAS, fator R, sublimite)
/fiscal/apuracao                 ← Apuração detalhada
/fiscal/apuracao/[ano]/[mes]    ← Histórico
/fiscal/guias                    ← Guias geradas (DAS, DARF) com botão pagar
/fiscal/simulador                ← Simules vs Presumido vs Real
/fiscal/reforma-tributaria       ← Dashboard CBS/IBS 2026

/notas                           ← Lista (entrada + saída)
/notas/entrada                   ← NFs recebidas, manifesto
/notas/saida                     ← NFs emitidas
/notas/saida/nova                ← Emissor de NF mock
/notas/[chave]                   ← Detalhe + DANFE mock

/contabil                        ← Balancete do mês
/contabil/lancamentos            ← Livro diário
/contabil/razao/[conta]          ← Razão por conta
/contabil/encerramento           ← Fechar período

/controles                       ← Fluxo de caixa projetado
/controles/pagar                 ← Contas a pagar (CRUD)
/controles/receber               ← Contas a receber (CRUD)
/controles/ativos                ← Imobilizado
/controles/bancos                ← Lista de contas conectadas
/controles/bancos/conectar       ← Open Finance mock (popup)

/pessoal                         ← Resumo da folha
/pessoal/funcionarios            ← Lista
/pessoal/funcionarios/novo       ← Admissão wizard
/pessoal/funcionarios/[id]       ← Ficha
/pessoal/folha/[ano]/[mes]       ← Folha detalhada
/pessoal/esocial                 ← Status eSocial mock

/relatorios/dre
/relatorios/balanco
/relatorios/dfc
/relatorios/indicadores

/compliance                      ← Painel
/compliance/certidoes            ← CND, CRF, FGTS
/compliance/intimacoes           ← e-CAC mock
/compliance/parcelamentos

/agenda                          ← Calendário fiscal
/assistente                      ← Chat IA mock (também é sidebar)

/configuracoes                   ← Hub
/configuracoes/empresa
/configuracoes/certificado
/configuracoes/integracoes
/configuracoes/usuarios
```

### 6.3 Sidebar — composição dinâmica por perfil

A sidebar **não mostra todas as rotas pra todos os perfis**. Renderiza baseado em `perfil.modulos` da empresa atual.

| Regime | Módulos visíveis |
|---|---|
| MEI | Início, Notas (saída), Fiscal (DAS-MEI), Agenda, Compliance, Configurações |
| Simples Nacional | Início, Fiscal, Notas, Contábil (parcial), Controles, Pessoal (se tem CLT), Relatórios, Compliance, Agenda, Configurações |
| Lucro Presumido | Tudo + ECD/ECF, EFD-Contribuições |
| Lucro Real | Tudo + LALUR, EFD-ICMS/IPI completa |

Módulos não-disponíveis pro perfil aparecem na sidebar **acinzentados com cadeado**, com tooltip "Disponível em planos superiores" — isso comunica visão completa do produto pro usuário sem confundir.

---

## 7. Schemas Zod — fonte da verdade

Todo dado do domínio tem schema Zod. Tipos TS são inferidos.

### 7.1 Empresa
```typescript
// src/lib/schemas/empresa.ts
import { z } from "zod";

export const regimeTributarioSchema = z.enum([
  "MEI",
  "SIMPLES_NACIONAL",
  "LUCRO_PRESUMIDO",
  "LUCRO_REAL",
]);

export const setorAtividadeSchema = z.enum([
  "COMERCIO",
  "INDUSTRIA",
  "SERVICOS",
  "MISTO",
]);

export const empresaSchema = z.object({
  id: z.string().uuid(),
  cnpj: z.string().regex(/^\d{14}$/),
  razaoSocial: z.string(),
  nomeFantasia: z.string().optional(),
  regime: regimeTributarioSchema,
  anexoSimples: z.enum(["I", "II", "III", "IV", "V"]).optional(),
  setor: setorAtividadeSchema,
  cnae: z.string(),
  uf: z.string().length(2),
  municipio: z.string(),
  inscricaoEstadual: z.string().optional(),
  inscricaoMunicipal: z.string().optional(),
  faturamento12m: z.number(),
  socios: z.array(
    z.object({
      cpf: z.string(),
      nome: z.string(),
      participacao: z.number().min(0).max(100),
      isAdministrador: z.boolean(),
    })
  ),
  certificadoA1: z
    .object({
      nomeArquivo: z.string(),
      validade: z.string().date(),
      mock: z.literal(true), // sempre true em mock
    })
    .optional(),
  bancosConectados: z.array(
    z.object({
      id: z.string(),
      banco: z.string(),
      apelido: z.string(),
      saldo: z.number(),
      ultimaSync: z.string().datetime(),
    })
  ),
  modulosAtivos: z.array(z.string()),
  criadoEm: z.string().datetime(),
});

export type Empresa = z.infer<typeof empresaSchema>;
export type RegimeTributario = z.infer<typeof regimeTributarioSchema>;
```

### 7.2 Fiscal — apuração
```typescript
// src/lib/schemas/fiscal.ts
import { z } from "zod";

export const apuracaoFiscalSchema = z.object({
  periodo: z.object({ ano: z.number(), mes: z.number() }),
  faturamentoMes: z.number(),
  faturamento12m: z.number(),
  sublimiteEstadual: z.number(), // 3.6M
  tetoSimples: z.number(),       // 4.8M

  // só pra Simples
  fatorR: z
    .object({
      valor: z.number(), // 0–1
      anexoAtual: z.enum(["III", "V"]),
      atencao: z.boolean(), // se < 28% e ainda no III
    })
    .optional(),

  aliquotaEfetiva: z.number(),
  valorDAS: z.number(),
  vencimento: z.string().date(),
  status: z.enum(["calculado", "pago", "atrasado", "em_aberto"]),

  composicao: z.array(
    z.object({
      tributo: z.string(), // ex: "IRPJ", "CSLL", "CPP", "ICMS", "ISS"
      valor: z.number(),
      percentual: z.number(),
    })
  ),

  alertas: z.array(
    z.object({
      tom: z.enum(["info", "warn", "error"]),
      titulo: z.string(),
      descricao: z.string(),
      acao: z.object({ label: z.string(), rota: z.string() }).optional(),
    })
  ),
});

export type ApuracaoFiscal = z.infer<typeof apuracaoFiscalSchema>;
```

### 7.3 Fiscal Health Score
```typescript
export const fiscalHealthSchema = z.object({
  score: z.number().min(0).max(100),
  tom: z.enum(["ok", "warn", "error"]), // verde/amarelo/vermelho
  titulo: z.string(), // ex: "Tudo em dia"
  componentes: z.array(
    z.object({
      categoria: z.enum([
        "obrigacoes_em_dia",
        "certidoes_validas",
        "sem_intimacoes",
        "fator_r_seguro",
        "sublimite_seguro",
        "conciliacao_em_dia",
      ]),
      pontuacao: z.number().min(0).max(100),
      tom: z.enum(["ok", "warn", "error"]),
      mensagem: z.string(),
    })
  ),
  alertasPrioritarios: z.array(
    z.object({
      tom: z.enum(["warn", "error"]),
      titulo: z.string(),
      descricao: z.string(),
      acao: z.object({ label: z.string(), rota: z.string() }),
    })
  ).max(3),
});
```

### 7.4 Demais schemas

Listar pelo menos: `notaFiscalSchema`, `lancamentoContabilSchema`, `contaBancariaSchema`, `transacaoBancariaSchema`, `funcionarioSchema`, `holeriteSchema`, `eventoEsocialSchema`, `obrigacaoFiscalSchema`, `certidaoSchema`, `intimacaoSchema`, `mensagemAssistenteSchema`, `simulacaoRegimeSchema`, `impactoReformaSchema`.

**Cada um deve estar implementado antes de qualquer componente que o consuma.** Schema primeiro, sempre.

---


## 8. Schema do Dexie (IndexedDB)

```typescript
// src/lib/db/schema.ts
import Dexie, { type EntityTable } from "dexie";
import type { Empresa } from "@/lib/schemas/empresa";
import type { NotaFiscal } from "@/lib/schemas/notas";
import type { LancamentoContabil } from "@/lib/schemas/contabil";
import type { ContaBancaria, TransacaoBancaria } from "@/lib/schemas/controles";
import type { Funcionario, Holerite } from "@/lib/schemas/pessoal";
import type { ContaPagarReceber } from "@/lib/schemas/controles";
import type { MensagemAssistente } from "@/lib/schemas/assistente";
import type { Certidao, Intimacao } from "@/lib/schemas/compliance";
import type { ObrigacaoFiscal } from "@/lib/schemas/fiscal";
import type { GuiaImposto } from "@/lib/schemas/fiscal";

export class AnalistaFiscalDB extends Dexie {
  empresas!: EntityTable<Empresa, "id">;
  notasFiscais!: EntityTable<NotaFiscal, "chave">;
  lancamentos!: EntityTable<LancamentoContabil, "id">;
  contasBancarias!: EntityTable<ContaBancaria, "id">;
  transacoes!: EntityTable<TransacaoBancaria, "id">;
  funcionarios!: EntityTable<Funcionario, "id">;
  holerites!: EntityTable<Holerite, "id">;
  contasPagarReceber!: EntityTable<ContaPagarReceber, "id">;
  mensagensAssistente!: EntityTable<MensagemAssistente, "id">;
  certidoes!: EntityTable<Certidao, "id">;
  intimacoes!: EntityTable<Intimacao, "id">;
  obrigacoes!: EntityTable<ObrigacaoFiscal, "id">;
  guias!: EntityTable<GuiaImposto, "id">;

  constructor() {
    super("AnalistaFiscalDB");
    this.version(1).stores({
      empresas: "id, cnpj, regime",
      notasFiscais: "chave, empresaId, [empresaId+tipo], emissao, status",
      lancamentos: "id, empresaId, [empresaId+data], conta, origem",
      contasBancarias: "id, empresaId, banco",
      transacoes: "id, contaId, [contaId+data], categoria",
      funcionarios: "id, empresaId, cpf, status",
      holerites: "id, [funcionarioId+ano+mes]",
      contasPagarReceber: "id, empresaId, [empresaId+tipo+status], vencimento",
      mensagensAssistente: "id, empresaId, [empresaId+criadoEm]",
      certidoes: "id, empresaId, tipo, vencimento",
      intimacoes: "id, empresaId, status, recebidoEm",
      obrigacoes: "id, empresaId, [empresaId+vencimento], status",
      guias: "id, empresaId, [empresaId+ano+mes], tipo, status",
    });
  }
}

export const db = new AnalistaFiscalDB();
```

### 8.1 Seed inicial — `src/lib/db/seed.ts`

Função `seedDemoEmpresa()` que:
1. Verifica se já tem empresa demo (`db.empresas.where('cnpj').equals('12345678000199').first()`).
2. Se não tem, cria:
   - 1 empresa: "FiscalAI Demo Ltda", CNPJ `12.345.678/0001-99`, Simples Nacional, Anexo III, Porto Alegre/RS, fundada há 14 meses, faturamento 12m R$ 850.000.
   - 6 sócios? Não — 2 sócios.
   - Certificado A1 mock (válido por 365 dias).
   - 3 bancos conectados (Itaú, Nubank, Bradesco) com saldos.
3. Gera 6 meses de NFs sintéticas usando faker:
   - ~30 NF-e emitidas/mês × 6 = 180 saída
   - ~80 NF-e recebidas/mês × 6 = 480 entrada
   - Variação realista: 5-15% mês a mês
4. Gera ~600 transações bancárias (60/mês × 3 contas × 6 meses fica muito; ajustar pra 30/conta/mês).
5. Gera 2 funcionários com 6 holerites cada.
6. Gera obrigações fiscais dos próximos 60 dias (DAS, FGTS, eSocial, DCTFWeb).
7. Gera 3 certidões (Federal/CND, FGTS/CRF, Trabalhista/CNDT) — todas vigentes.
8. Gera 1 intimação simulada do e-CAC (status "lida").

**Importante:** o seed roda apenas uma vez. Bandeira em `localStorage`: `analista-fiscal:seeded:v1`.

---

## 9. Mock API contracts — todos os endpoints

Lista canônica. Toda fase implementa um subconjunto. Cada endpoint documentado abaixo deve ter:
- Route Handler em `src/app/api/mock/<path>/route.ts`
- Função no `api-client.ts`
- Hook em `src/hooks/`
- Schema Zod validando entrada e saída

### 9.1 Empresa

```
GET  /api/mock/empresa/atual
POST /api/mock/empresa/cnpj-lookup        body: {cnpj} → puxa dados da Receita (mock)
POST /api/mock/empresa                    body: Empresa (criar/atualizar) — escreve no Dexie
PUT  /api/mock/empresa/regime              body: {regime, anexo}
```

### 9.2 Fiscal

```
GET  /api/mock/fiscal/saude              → FiscalHealthScore
GET  /api/mock/fiscal/apuracao/atual     → ApuracaoFiscal do mês corrente
GET  /api/mock/fiscal/apuracao/[ano]/[mes]
GET  /api/mock/fiscal/historico?meses=12  → array de apurações
GET  /api/mock/fiscal/guias              → guias do mês
POST /api/mock/fiscal/guias/gerar        body: {tipo, periodo} → cria guia mock
GET  /api/mock/fiscal/simulador          query: {faturamento, atividade, fator_r}
GET  /api/mock/fiscal/reforma/impacto    → ImpactoReforma
```

### 9.3 Notas (Dexie-backed)

```
GET    /api/mock/notas?tipo&inicio&fim&page
POST   /api/mock/notas/saida             body: NFInput → emite mock (gera chave, calcula impostos, salva no Dexie)
POST   /api/mock/notas/saida/[chave]/cancelar
GET    /api/mock/notas/[chave]
GET    /api/mock/notas/[chave]/danfe.pdf  → retorna PDF gerado por jsPDF
GET    /api/mock/notas/[chave]/xml        → retorna XML mock
```

### 9.4 Contábil

```
GET  /api/mock/contabil/balancete?ano&mes
GET  /api/mock/contabil/lancamentos?inicio&fim&conta&page
POST /api/mock/contabil/lancamentos       body: LancamentoInput
GET  /api/mock/contabil/razao/[conta]?ano&mes
POST /api/mock/contabil/encerramento      body: {ano, mes}
```

### 9.5 Controles (Dexie-backed)

```
GET    /api/mock/controles/fluxo-caixa?dias=90
GET    /api/mock/controles/pagar
POST   /api/mock/controles/pagar
PATCH  /api/mock/controles/pagar/[id]/marcar-pago
DELETE /api/mock/controles/pagar/[id]
GET    /api/mock/controles/receber
POST   /api/mock/controles/receber
PATCH  /api/mock/controles/receber/[id]/marcar-recebido
GET    /api/mock/controles/bancos
POST   /api/mock/controles/bancos/conectar    body: {bancoId, credenciais (mock)}
POST   /api/mock/controles/bancos/sync        body: {contaId} → simula refresh
GET    /api/mock/controles/bancos/[id]/transacoes
POST   /api/mock/controles/bancos/[id]/conciliar  body: {transacaoId, lancamentoId}
```

### 9.6 Pessoal (Dexie-backed)

```
GET    /api/mock/pessoal/folha/[ano]/[mes]
POST   /api/mock/pessoal/folha/[ano]/[mes]/processar  → simula cálculo
GET    /api/mock/pessoal/funcionarios
POST   /api/mock/pessoal/funcionarios                  body: FuncionarioInput
GET    /api/mock/pessoal/funcionarios/[id]
GET    /api/mock/pessoal/funcionarios/[id]/holerites
GET    /api/mock/pessoal/holerites/[id]/pdf
GET    /api/mock/pessoal/esocial/eventos?status
POST   /api/mock/pessoal/esocial/transmitir            body: {eventos[]}
```

### 9.7 Compliance

```
GET  /api/mock/compliance/painel              → status geral
GET  /api/mock/compliance/certidoes           → lista CND, CRF, CNDT
POST /api/mock/compliance/certidoes/emitir    body: {tipo} → gera mock
GET  /api/mock/compliance/intimacoes
PATCH /api/mock/compliance/intimacoes/[id]/marcar-lida
GET  /api/mock/compliance/parcelamentos
```

### 9.8 Agenda

```
GET /api/mock/agenda?inicio&fim    → eventos do calendário fiscal
```

### 9.9 Assistente IA mock

```
GET  /api/mock/assistente/conversas
POST /api/mock/assistente/conversas/[id]/mensagens   body: {texto}
                                                      → retorna resposta mock baseada em padrões
```

Resposta do assistente é **mockada com regras simples**, não LLM real:
- Se contém "DAS" → retorna apuração atual com citação
- Se contém "fluxo" ou "caixa" → retorna projeção 30/60/90 dias
- Se contém "fator R" → retorna análise mock
- Se contém "imposto" → retorna composição
- Default → retorna mensagem genérica explicando capacidades

Em todos os casos, resposta tem **citação** (igual ao princípio do produto real).

---

## 10. Roadmap de implementação — 13 fases

> **Regra de ouro:** uma fase por vez. Cada fase termina com critério de aceitação binário. Só passa pra próxima quando todos passam.

### Fase 0 — Setup (½ dia)

**Entregas:**
- [ ] Repositório criado: `analista-fiscal-web/`
- [ ] Next.js 15 inicializado: `npx create-next-app@latest analista-fiscal-web --typescript --tailwind --app --src-dir --import-alias "@/*" --no-eslint`
- [ ] Tailwind CSS v4 funcionando (substituir `tailwind.config.ts` por nada — v4 é zero-config).
- [ ] shadcn inicializado: `npx shadcn@canary init` — escolher tema "Slate" (vamos sobrescrever).
- [ ] Dependências instaladas:
  ```
  pnpm add @tanstack/react-query @tanstack/react-table zustand react-hook-form zod @hookform/resolvers
  pnpm add recharts date-fns date-fns-tz dexie
  pnpm add @faker-js/faker jspdf jsbarcode qrcode
  pnpm add sonner vaul cmdk nuqs framer-motion
  pnpm add -D @types/qrcode prettier eslint-config-prettier
  ```
- [ ] `tsconfig.json` com strict mode + `noUncheckedIndexedAccess`.
- [ ] `.prettierrc` com `printWidth: 100, semi: true, singleQuote: false`.
- [ ] Estrutura de pastas criada (vazia, mas existente — seguir item 4).
- [ ] `globals.css` com tokens fiscalai_v4 (item 5.1).
- [ ] Fontes Plus Jakarta Sans + JetBrains Mono via `next/font/google` no root layout.
- [ ] `next.config.mjs` com `experimental.reactCompiler: true`.

**Critério:** `pnpm dev` sobe em http://localhost:3000 mostrando uma página em branco com fundo `#06080f` e o grid pattern lime visível.

---

### Fase 1 — Design system + shell (1.5 dias)

**Entregas:**
- [ ] Adicionar primitives shadcn (lista 5.3): `npx shadcn@canary add button input label card dialog drawer dropdown-menu select tabs badge tooltip popover command sheet accordion alert skeleton separator switch checkbox radio-group progress scroll-area sonner`
- [ ] **Customizar TODAS as primitives** pra usar nossos tokens. Substituir `bg-background`, `text-foreground` por `bg-bg`, `text-txt`. Trocar `primary` por `lime`. (Detalhar em snippet anexo se necessário, mas Claude Code deve aplicar sistematicamente.)
- [ ] Criar `src/components/shared/`:
  - [ ] `Moeda` (item 5.4)
  - [ ] `Pill` (item 5.4)
  - [ ] `StatCard`
  - [ ] `EmptyState`, `LoadingState`, `ErrorState`
  - [ ] `DataBR` (formata data BR)
  - [ ] `MonoNumber` (números monoespaçados, tabular)
- [ ] Criar `src/lib/format/` (`moeda.ts`, `cnpj.ts`, `cpf.ts`, `data.ts`, `numero.ts`).
- [ ] Criar layout shell: `src/app/(dashboard)/layout.tsx`:
  - [ ] `<Sidebar />` à esquerda (largura 224px, igual fiscalai_v4)
  - [ ] `<Topbar />` no topo (altura 56px) com: logo + nome empresa + assistente button + avatar
  - [ ] `<AlertasFlutuantes />` no canto inferior direito (toasts)
  - [ ] `<main>` com padding e max-width 1280px
- [ ] Sidebar com navegação completa, mas itens bloqueados por perfil aparecem com `Lock` icon e tooltip.
- [ ] Topbar com command palette (cmdk): `Cmd+K` abre busca global mock.
- [ ] Setup providers globais em `app/layout.tsx`:
  - [ ] `QueryClientProvider`
  - [ ] `Toaster` do sonner
  - [ ] `EmpresaProvider` (carrega empresa atual do Dexie ou redireciona pra onboarding)

**Critério:** `/home` mostra shell completo (sidebar + topbar + área central vazia). `Cmd+K` abre command palette com placeholder. Sidebar visualmente idêntica ao fiscalai_v4.html.

---

### Fase 2 — Auth mock + Onboarding completo (2 dias)

**Entregas:**

#### Login (`/login`)
- [ ] Tela igual ao `#auth` do fiscalai_v4 (logo hexagonal, dois tabs Entrar/Criar conta).
- [ ] Login fake: qualquer email/senha funciona. Salva flag `analista-fiscal:logado` em localStorage.
- [ ] "Demo: demo@fiscalai.com / demo123" como hint.
- [ ] Após login, se Dexie tem empresa → redirect `/home`. Se não → `/onboarding`.

#### Onboarding (`/onboarding`)
Wizard 5 passos com progress bar no topo:

**Passo 1 — CNPJ**
- [ ] Input CNPJ com máscara automática.
- [ ] Botão "Buscar dados" → chama `/api/mock/empresa/cnpj-lookup` → simula 1.2s de loading → retorna razão social, endereço, CNAE, atividades secundárias mockadas.
- [ ] Mostra dados encontrados em card lime, com opção "Confirmar".

**Passo 2 — Regime tributário**
- [ ] 4 cards (MEI, Simples, Presumido, Real) com descrição e limite.
- [ ] Se Simples selecionado → revela seleção de Anexo (I-V) com explicação plain-portuguese de cada.
- [ ] "Não sei meu regime" → botão que abre modal com 3 perguntas (faturamento, atividade, número de funcionários) e sugere o mais provável.

**Passo 3 — Certificado digital A1**
- [ ] Dropzone igual ao `.dropz` do fiscalai_v4.
- [ ] Aceita qualquer arquivo `.pfx` ou `.p12`. Não valida nada.
- [ ] "Senha do certificado" — input password, qualquer valor aceito.
- [ ] Botão "Pular por enquanto" disponível.
- [ ] Após upload mock, mostra "✓ Certificado FiscalAI Demo Ltda válido até 08/05/2027".

**Passo 4 — Conectar bancos (Open Finance mock)**
- [ ] Grid com 6 bancos (Itaú, Bradesco, BB, Santander, Nubank, Inter) com logos SVG.
- [ ] Clicar abre **modal mock que imita popup OAuth**: barra de carregamento "Conectando ao Itaú via Open Finance..." → "Autorizando acesso..." → "✓ Conectado" (3 segundos total).
- [ ] Pode conectar múltiplos. Ou pular.

**Passo 5 — Conclusão**
- [ ] Resumo: "Você é Simples Nacional Anexo III, faturamento R$X. Seu próximo DAS é R$Y, vence dia Z."
- [ ] CTA "Ir pro meu painel".

**Comportamento técnico:**
- [ ] Cada passo persiste no Dexie ao avançar (não só ao final).
- [ ] Botão "Voltar" funciona em todos os passos.
- [ ] Estado do wizard em Zustand store (`wizardOnboardingStore`).

**Critério:** Fluxo onboarding completo do `/login` até dashboard funciona end-to-end. Após F5, empresa cadastrada persiste. Reset: botão escondido `Cmd+Shift+R` em `/configuracoes` que limpa Dexie e localStorage.

---

### Fase 3 — Dashboard home (1.5 dias)

A tela mais importante do app. Aplicar rigorosamente as 5 leis de UX.

**Entregas:**
- [ ] Componente `<FiscalHealthScore />` no topo:
  - [ ] Score grande (96px), font-weight 800, mono.
  - [ ] Cor dinâmica: ≥80 lime, 60-79 amber, <60 red.
  - [ ] Frase headline plain-portuguese: "Tudo em dia" / "Atenção em alguns pontos" / "Ação urgente".
  - [ ] Barra de progresso embaixo.
- [ ] Card "Próximo pagamento" — DAS do mês com valor, vencimento, botão "Ver guia".
- [ ] Card "Próxima obrigação" — ex: "Entregar PGDAS-D até dia 20".
- [ ] Card "Alertas" (max 3) — cada um com título + 1 botão de ação.
- [ ] Calendário visual do mês com dias coloridos (verde pago / amarelo a fazer / vermelho atrasado).
- [ ] Gráfico Recharts: receita × imposto últimos 6 meses (linhas).
- [ ] Quick actions (4 cards) — emitir NF, ver folha, ver fluxo, ver assistente.
- [ ] Card "Você no Simples Nacional": faturamento 12m / sublimite, com barra de progresso.

**Mock:** `/api/mock/fiscal/saude` retorna score 87 (lime), com 1 alerta amber sobre Fator R em 32% (tendência de queda).

**Critério:** Tela carrega em <1s, mostra dados realistas, 3 leis aplicadas (sem códigos fiscais visíveis, status antes de números, todo alerta com ação).

---

### Fase 4 — Módulo Fiscal (2 dias)

**Entregas:**

#### `/fiscal` (apuração do mês)
- [ ] Apuração detalhada do mês corrente:
  - [ ] Faturamento, alíquota efetiva, valor DAS.
  - [ ] Composição (donut chart Recharts) — IRPJ, CSLL, CPP, ISS, etc. Cada fatia tem nome humano, não sigla isolada.
  - [ ] Botão "Gerar guia DAS".
- [ ] Card Fator R (se Simples Anexo III/V).
- [ ] Card Sublimite estadual.
- [ ] Card Teto Simples (4.8M).
- [ ] Histórico — gráfico 12 meses + lista clicável.

#### `/fiscal/guias`
- [ ] Lista das guias geradas (DAS atual + DAS dos meses anteriores).
- [ ] Botão "Gerar PDF" → chama jsPDF, baixa arquivo `DAS-MM-YYYY.pdf` com:
  - [ ] Logo "FiscalAI"
  - [ ] CNPJ, razão social
  - [ ] Período de apuração
  - [ ] Valor
  - [ ] Código de barras gerado por jsbarcode (44 dígitos mock)
  - [ ] Data vencimento
- [ ] Botão "Pagar via PIX" → modal com QR Code mock (qrcode lib) + "Copia e cola".

#### `/fiscal/simulador`
- [ ] Form: faturamento anual, atividade (CNAE simplificado), número funcionários.
- [ ] Output: comparação Simples vs Presumido vs Real em cards lado a lado.
- [ ] Cada card mostra: imposto total, % sobre faturamento, recomendação (lime se vantajoso, amber se neutro).
- [ ] Gráfico de barras agrupadas com a comparação.

#### `/fiscal/reforma-tributaria`
- [ ] Banner explicativo: "A partir de 2026, o sistema tributário muda. Simulamos o impacto na sua empresa."
- [ ] Linha do tempo da Reforma (2026-2033).
- [ ] Card "Impacto estimado" com setas indicando se vai pagar mais/menos.
- [ ] Tabela "Antes vs Depois" com PIS+COFINS → CBS, ICMS+ISS → IBS.

**Critério:** Todas as telas renderizam com dados consistentes. PDF do DAS abre. Simulador retorna 3 cenários comparados em <500ms.

---

### Fase 5 — Módulo Notas (3 dias)

A maior fase. NF-e é o coração do produto.

**Entregas:**

#### `/notas` (lista geral)
- [ ] TanStack Table com colunas: tipo (entrada/saída pill), número, contraparte, valor, data, status.
- [ ] Filtros (com nuqs): período, tipo, status, busca por contraparte/número.
- [ ] Paginação (50/página).
- [ ] Ações por linha: ver, baixar XML, baixar DANFE.

#### `/notas/saida/nova` — Emissor de NF-e mock
Wizard 4 passos:

**Passo 1 — Destinatário**
- [ ] Input CNPJ ou CPF.
- [ ] Botão "Buscar" → mock retorna dados.
- [ ] Ou "Cadastrar novo cliente" inline.

**Passo 2 — Produtos/serviços**
- [ ] Adicionar itens (autocomplete que busca em catálogo mock).
- [ ] Para cada item: descrição, quantidade, valor unitário.
- [ ] **Sistema calcula automaticamente** CFOP, CST/CSOSN, NCM, alíquotas. Tudo invisível ao usuário (lei UX 1).
- [ ] Total da nota se atualiza em tempo real.

**Passo 3 — Pagamento**
- [ ] Forma de pagamento (PIX, boleto, dinheiro, cartão).
- [ ] Vencimento.

**Passo 4 — Conferência + emissão**
- [ ] Resumo legível: "Você está vendendo X reais em produtos para Empresa Y. Imposto incluso: Z reais."
- [ ] Botão grande "Emitir nota fiscal".
- [ ] Loading 2-3s simulando comunicação com SEFAZ.
- [ ] Sucesso: animação check + "Nota fiscal emitida com sucesso".
- [ ] Mostra chave de acesso, oferece "Baixar DANFE" e "Baixar XML".
- [ ] Salva no Dexie. Aparece imediatamente em `/notas`.

#### `/notas/[chave]` — Detalhe
- [ ] Visualização DANFE-like (não precisa ser layout oficial; pode ser a versão FiscalAI bonita).
- [ ] Botões: baixar PDF, baixar XML, cancelar (se <7 dias), correção (mock).

#### `/notas/entrada` — Manifesto
- [ ] Lista de NFs recebidas com status: confirmada, pendente_manifesto, ciente.
- [ ] Botão "Manifestar" → modal com 4 opções (Confirmação, Ciência, Desconhecimento, Operação não realizada).

#### Geração de DANFE PDF (`src/lib/pdf/danfe.ts`)
- [ ] jsPDF com layout A4 simplificado mas profissional.
- [ ] Cabeçalho com logo + razão social + CNPJ + chave (44 dígitos com espaços).
- [ ] Bloco destinatário, bloco itens (tabela), totais, infos adicionais.
- [ ] Código de barras com jsbarcode na chave.

**Critério:** Emissão completa funciona. NF emitida persiste após F5. PDF abre com layout DANFE-like. Lista atualiza com optimistic update.

---

### Fase 6 — Módulo Contábil (2 dias)

**Entregas:**

#### `/contabil` — Balancete
- [ ] Tabela hierárquica: Ativo → Circulante → Caixa, Bancos, Clientes, etc.
- [ ] Colunas: saldo anterior, débitos, créditos, saldo atual.
- [ ] Cores: ativo lime, passivo amber.
- [ ] Toggle "Esconder contas zeradas".
- [ ] Validação visual: total débitos = total créditos. Se não bate, banner red.

#### `/contabil/lancamentos` — Livro Diário
- [ ] Lista cronológica de partidas dobradas.
- [ ] Filtros (período, conta, origem).
- [ ] Origem com pill: NF saída (lime), NF entrada (blue), bancário (amber), folha (purple), manual (cinza).
- [ ] Modal de criação manual: data, conta débito, conta crédito, valor, histórico.
- [ ] Lançamentos com confidence baixa (mock: gerar alguns flagged) aparecem com `AlertTriangle` amber.

#### `/contabil/razao/[conta]` — Razão analítico
- [ ] Movimento de uma conta específica.
- [ ] Saldo acumulado em cada linha.
- [ ] Botão imprimir (CSS @media print).

#### `/contabil/encerramento`
- [ ] Botão "Fechar dezembro/2025" (ou mês atual).
- [ ] Loading mock, depois mostra: "Resultado do exercício: Lucro de R$ X. Distribuído conforme contrato social."

**Critério:** Balancete fecha (débito = crédito). Razão de uma conta soma corretamente. Lançamentos manuais aparecem no Razão da conta correspondente.

---

### Fase 7 — Módulo Controles + Open Finance mock (2.5 dias)

**Entregas:**

#### `/controles/bancos`
- [ ] Lista de contas conectadas com saldo, banco logo, última sincronização.
- [ ] Botão "Sincronizar agora" — loading 1.5s, atualiza saldo (faker).
- [ ] Botão "Conectar nova conta" → `/controles/bancos/conectar`.

#### `/controles/bancos/conectar`
- [ ] Grid de bancos suportados (mesma lista do onboarding).
- [ ] Clicar abre modal **Open Finance mock**:
  1. "Você será redirecionado pro app do [Banco]..." (1s)
  2. Tela mock que imita autorização do banco (logo do banco, "Autorize FiscalAI a acessar suas contas") (espera click)
  3. Dois botões "Autorizar" e "Recusar"
  4. Se autorizar → "Aguarde, sincronizando..." (2s) → "✓ Conta XX-YY-Z conectada"
- [ ] Conta nova aparece na lista, com 30 dias de transações mock.

#### `/controles` — Fluxo de caixa
- [ ] Gráfico Recharts area chart com 90 dias projetados.
- [ ] Cards: saldo hoje, saldo previsto 30d / 60d / 90d.
- [ ] Alertas se saldo previsto vai negativo.

#### `/controles/pagar` — Contas a pagar
- [ ] CRUD completo. Modal de criação com: descrição, fornecedor, valor, vencimento, categoria.
- [ ] Status: pendente (amber), pago (lime), atrasado (red).
- [ ] Ações: marcar pago, editar, excluir.
- [ ] Filtros: status, vencimento.

#### `/controles/receber` — Idem ao pagar.

#### `/controles/bancos/[id]` — Extrato + conciliação
- [ ] Extrato bancário com transações.
- [ ] Coluna "Conciliado": ícone check lime se já conciliado, vazio se não.
- [ ] Clicar em transação não-conciliada abre modal: lista lançamentos contábeis sugeridos (matching por valor ± 1%).
- [ ] Botão "Conciliar" — vincula e fecha modal.

**Critério:** Conectar banco mock funciona. Transações persistem. Conciliar vincula transação a lançamento (Dexie). Fluxo de caixa atualiza ao adicionar conta a pagar.

---

### Fase 8 — Módulo Pessoal (2.5 dias)

**Entregas:**

#### `/pessoal` — Resumo da folha do mês
- [ ] Card "Folha de novembro/2025": total bruto, total líquido, INSS patronal, FGTS.
- [ ] Lista de funcionários com salário e status do holerite (gerado/pago).
- [ ] Card "eSocial": status (verde se transmitido, amber se pendente).

#### `/pessoal/funcionarios`
- [ ] Lista com avatar (faker), nome, cargo, salário, data admissão.
- [ ] Filtros: status (ativo, demitido, afastado).

#### `/pessoal/funcionarios/novo` — Wizard admissão
3 passos: dados pessoais → contrato (CLT, PJ, estágio) → vínculo (cargo, salário, jornada).
- [ ] Ao salvar, gera evento eSocial S-2200 mock e mostra: "Admissão registrada. Evento eSocial S-2200 transmitido com sucesso (recibo: ABC123)."

#### `/pessoal/folha/[ano]/[mes]`
- [ ] Tabela com todos funcionários, eventos da folha (proventos/descontos), totais.
- [ ] Botão "Gerar holerites em PDF" → loop em jsPDF, zip download (jszip não, baixa um por um por simplicidade).
- [ ] Botão "Transmitir ao eSocial" → loading 3s → "✓ 5 eventos transmitidos".

#### Holerite PDF (`src/lib/pdf/holerite.ts`)
- [ ] Layout: cabeçalho empresa, dados funcionário, eventos (cód, descrição, referência, proventos, descontos), totais.

#### `/pessoal/esocial`
- [ ] Lista de eventos transmitidos com status.
- [ ] Eventos com erro (mock: 1 deles em vermelho) com botão "Reenviar".

**Critério:** Admitir funcionário cria holerites simulados. PDF do holerite abre. Lista de eSocial mostra eventos do mês.

---

### Fase 9 — Módulo Relatórios (1.5 dias)

**Entregas:**

#### `/relatorios/dre`
- [ ] DRE comparativo (mês atual vs mês anterior vs mesmo mês ano passado).
- [ ] Estrutura: Receita Bruta → Deduções → Receita Líquida → CMV → Lucro Bruto → Despesas → Resultado Operacional → Lucro Líquido.
- [ ] Margens em destaque (margem bruta, operacional, líquida) com pill colorido.

#### `/relatorios/balanco`
- [ ] Balanço Patrimonial em 2 colunas: Ativo | Passivo + PL.
- [ ] Validação visual: Ativo = Passivo + PL. Banner red se não bate.

#### `/relatorios/dfc`
- [ ] DFC método indireto.
- [ ] Atividades operacionais, investimento, financiamento.

#### `/relatorios/indicadores`
- [ ] Cards com KPIs: liquidez corrente, endividamento, ROI, ROE, ticket médio, prazo médio recebimento, etc.
- [ ] Cada KPI com mini-gráfico sparkline (Recharts) dos últimos 12 meses.

**Critério:** Todos os 4 relatórios renderizam com números consistentes derivados do balancete e folha.

---

### Fase 10 — Compliance + Agenda (1.5 dias)

**Entregas:**

#### `/compliance` — Painel
- [ ] 4 cards principais: Certidões (3 vigentes), Intimações (1 lida), Parcelamentos (0), CNPJ (ativo).

#### `/compliance/certidoes`
- [ ] Lista: CND Federal, CRF FGTS, CNDT Trabalhista.
- [ ] Status, data emissão, vencimento (com countdown amber se <30d).
- [ ] Botão "Renovar" → loading mock + nova certidão.

#### `/compliance/intimacoes`
- [ ] Lista (1 mock).
- [ ] Modal de detalhe com texto da intimação mock + botão "Marcar como lida" + "Enviar pra meu contador" (mock).

#### `/compliance/parcelamentos`
- [ ] Empty state: "Nenhum débito parcelado. Sua situação está limpa."

#### `/agenda`
- [ ] Calendário mensal (FullCalendar não — vamos com layout custom).
- [ ] Eventos do mês com cores: pago (lime), pendente (amber), atrasado (red), informativo (blue).
- [ ] Lista lateral com próximos 7 eventos.
- [ ] Toggle: ver mês / ver lista anual.

**Critério:** Compliance hub renderiza certidões. Renovar gera nova mock. Agenda mostra eventos do calendário fiscal customizado pro perfil da empresa demo.

---

### Fase 11 — Assistente IA mock (1.5 dias)

**Entregas:**

#### `/assistente` — Página dedicada
- [ ] Layout chat: histórico em scroll, input fixo embaixo.
- [ ] Mensagens do user à direita (card-2), do assistente à esquerda (card com border lime).
- [ ] Toda mensagem do assistente tem citações: "📄 apuracao-2025-11-001" clicável.
- [ ] Quick replies: "Quanto pago de DAS?", "Como está meu fluxo?", "Tem alguma intimação?".

#### Chat sidebar (presente em TODAS as páginas)
- [ ] Botão flutuante "💬 Perguntar" no canto inferior direito.
- [ ] Click abre Sheet (shadcn) à direita com mesmo chat compactado.

#### Mock de respostas (`src/lib/mocks/assistente.ts`)
Função `gerarResposta(pergunta: string, contexto: ContextoEmpresa)` com regras:
- [ ] Contém "DAS" ou "imposto" → lê apuração do Dexie/seed → retorna valor + composição em texto natural + citação.
- [ ] Contém "fluxo" ou "caixa" → lê transações dos últimos 30 dias + projeta 30 dias → retorna 2-3 frases + gráfico inline.
- [ ] Contém "fator R" → analisa folha + faturamento → retorna percentual + comparação com 28%.
- [ ] Contém "certidão" → status das certidões.
- [ ] Default → mensagem com 4 sugestões clicáveis.

Resposta do bot tem **delay simulado de digitação** (typing indicator 800-1500ms) antes de aparecer.

**Critério:** 5 perguntas testadas retornam resposta plausível com citação. Chat persiste em Dexie (reload mantém histórico).

---

### Fase 12 — Configurações (1 dia)

**Entregas:**

#### `/configuracoes`
- [ ] Hub com 4 cards: Empresa, Certificado, Integrações, Usuários.

#### `/configuracoes/empresa`
- [ ] Form editável: razão social, nome fantasia, regime, anexo, endereço.
- [ ] Botão "Salvar" → atualiza Dexie.

#### `/configuracoes/certificado`
- [ ] Mostra info do A1 atual (mock).
- [ ] Botão "Substituir" — abre dropzone.

#### `/configuracoes/integracoes`
- [ ] Lista de integrações mock: Open Finance (3 bancos conectados), e-CAC (não conectado), eSocial, Receita Federal.
- [ ] Cada uma com toggle on/off (visual apenas).

#### `/configuracoes/usuarios`
- [ ] Lista com 1 usuário (você). Convite mock disponível.

#### Botão Reset (escondido)
- [ ] No rodapé de `/configuracoes`, com texto pequeno: "Limpar dados de demonstração". Confirma e zera Dexie + localStorage. Redireciona pra `/onboarding`.

**Critério:** Editar empresa persiste. Reset funciona e recomeça do zero.

---

### Fase 13 — Polish + responsivo + animações (1.5 dias)

**Entregas:**
- [ ] Revisar TODAS as telas em viewport mobile (< 700px) seguindo media queries do fiscalai_v4.
- [ ] Sidebar vira drawer no mobile (vaul).
- [ ] Tabelas com scroll horizontal em mobile.
- [ ] Animações de entrada de página (framer-motion fade + slide 8px).
- [ ] Loading states com skeleton em todas as listas.
- [ ] Error states com botão "Tentar de novo".
- [ ] Empty states com ilustração SVG simples + CTA.
- [ ] Microinterações: hover dos cards (translateY -2px), transição smooth.
- [ ] Toast de sucesso ao emitir NF, conectar banco, salvar configuração.
- [ ] 404 page com identidade visual.
- [ ] Otimização: lazy load de Recharts e jsPDF (dynamic imports).
- [ ] Lighthouse: rodar e garantir performance > 80.
- [ ] Acessibilidade básica: navegação por teclado funciona, focus visible.

**Critério:** Demo completa flui sem quebras. Mobile usável. Sem console errors. Lighthouse Performance ≥80, Accessibility ≥90.

---

## 11. Critérios globais de aceitação (final do projeto)

Ao final das 13 fases:

1. ✅ `pnpm dev` sobe sem erros.
2. ✅ Login → Onboarding → Dashboard funciona end-to-end.
3. ✅ Empresa demo cadastrada persiste após F5.
4. ✅ Todas as 50+ rotas respondem (sem 404 dentro do app).
5. ✅ Emitir NF-e mock funciona, persiste, gera PDF.
6. ✅ Conectar banco via Open Finance mock funciona.
7. ✅ Folha de pagamento gera holerites em PDF.
8. ✅ Assistente IA responde 5 perguntas-chave com citação.
9. ✅ Sidebar respeita perfil (módulos bloqueados aparecem com cadeado).
10. ✅ Identidade visual do fiscalai_v4 reproduzida (cores, fontes, espaçamentos).
11. ✅ Zero `any` em TypeScript. Zero erros do tsc strict.
12. ✅ Mobile usável.
13. ✅ Reset funciona e zera estado.
14. ✅ Critério qualitativo: dono de restaurante entenderia cada tela em 5s.

---

## 12. Como o Claude Code deve operar

1. **Ler este documento inteiro antes de codar uma linha.**
2. **Implementar fase por fase, em ordem.** Nada de pular.
3. **Cada fase começa criando branch:** `git checkout -b fase-N-nome-da-fase`.
4. **Cada fase termina com commit** descritivo: `feat(fase-3): dashboard home com fiscal health score`.
5. **Não criar arquivos fora da estrutura de pastas definida no item 4.**
6. **Não adicionar dependências fora da lista do item 2.1** sem perguntar.
7. **Schemas Zod sempre primeiro.** Antes do componente, do hook, do route handler.
8. **Quando ambiguidade aparecer:** preferir o que está mais próximo do `fiscalai_v4.html` visualmente, e do que está nas 5 leis de UX comportamentalmente.
9. **Nunca mostrar códigos fiscais ao usuário.** Lei 1, inviolável.
10. **Em qualquer dúvida sobre cálculo de imposto:** os valores são mock, não precisa estar correto fiscalmente. Realismo > exatidão. Use faker + heurísticas (DAS = faturamento × ~7-9% pra Anexo III).
11. **Reportar ao final de cada fase:** lista de arquivos criados, screenshot textual do que foi entregue, qualquer decisão tomada que não estava no plano.
12. **Não rodar build em produção.** Não fazer deploy. Apenas `pnpm dev`.

---

## 13. Snippets críticos (referência)

### 13.1 `src/lib/mocks/utils.ts`

```typescript
import { faker } from "@faker-js/faker/locale/pt_BR";

export async function mockLatency(min = 150, max = 400): Promise<void> {
  const ms = Math.floor(Math.random() * (max - min + 1)) + min;
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function mockMaybeError(probability = 0.02): void {
  if (Math.random() < probability) {
    throw new Error("MOCK_RANDOM_ERROR");
  }
}

faker.seed(42); // determinismo para empresa demo
export { faker };
```

### 13.2 `src/lib/db/index.ts`

```typescript
import { AnalistaFiscalDB } from "./schema";
export const db = new AnalistaFiscalDB();

if (typeof window !== "undefined") {
  // garante que o DB existe antes de qualquer query
  db.open().catch((err) => console.error("Dexie open failed:", err));
}
```

### 13.3 `src/lib/query-client.ts`

```typescript
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
```

### 13.4 `src/components/ui/button.tsx` — variantes customizadas

```tsx
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-bold text-sm transition-all disabled:opacity-40 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime/40",
  {
    variants: {
      variant: {
        default: "bg-lime text-bg hover:brightness-110 hover:-translate-y-px",
        secondary: "bg-blue text-white hover:brightness-110",
        ghost: "text-txt-2 hover:text-txt hover:bg-card-2",
        outline: "border border-line-2 text-txt hover:border-lime hover:text-lime bg-transparent",
        destructive: "bg-red text-white hover:brightness-110",
      },
      size: {
        default: "h-10 px-5",
        sm: "h-8 px-3 text-xs",
        lg: "h-12 px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);
```

### 13.5 Estrutura do EmpresaProvider

```tsx
// src/components/empresa-provider.tsx
"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { db } from "@/lib/db";
import { seedDemoEmpresa } from "@/lib/db/seed";
import type { Empresa } from "@/lib/schemas/empresa";

const EmpresaCtx = createContext<{
  empresa: Empresa | null;
  loading: boolean;
  trocar: (id: string) => void;
} | null>(null);

export function EmpresaProvider({ children }: { children: React.ReactNode }) {
  const [empresa, setEmpresa] = useState<Empresa | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      await seedDemoEmpresa();
      const empresas = await db.empresas.toArray();
      const ativaId = localStorage.getItem("analista-fiscal:empresa-ativa");
      const escolhida =
        empresas.find((e) => e.id === ativaId) ?? empresas[0] ?? null;
      setEmpresa(escolhida);
      setLoading(false);
    })();
  }, []);

  // ...
}

export function useEmpresaAtual() {
  const ctx = useContext(EmpresaCtx);
  if (!ctx) throw new Error("useEmpresaAtual fora de provider");
  return ctx;
}
```

### 13.6 Padrão de página com TanStack Query

```tsx
// src/app/(dashboard)/fiscal/page.tsx
"use client";

import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { ApuracaoCard } from "@/components/fiscal/apuracao-card";
import { LoadingState, ErrorState } from "@/components/shared";

export default function FiscalPage() {
  const { data, isLoading, error, refetch } = useApuracaoAtual();

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState onRetry={refetch} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <ApuracaoCard apuracao={data} />
      {/* ... */}
    </div>
  );
}
```

### 13.7 Pattern de Route Handler com Dexie (não funciona — Dexie é client-side)

⚠️ **Lembrete crítico:** Route Handlers rodam no Node, não têm acesso ao Dexie do browser. Pra dados que vivem no Dexie, o `api-client` chama o Dexie diretamente, **sem passar por Route Handler**. Conferir item 3.3.

```typescript
// EXEMPLO ERRADO (NÃO fazer):
// src/app/api/mock/notas/route.ts
// export async function GET() {
//   const notas = await db.notasFiscais.toArray(); // ❌ Dexie não existe aqui
// }

// EXEMPLO CORRETO:
// src/lib/api-client.ts
import { db } from "@/lib/db";
export const api = {
  notas: {
    listar: () => db.notasFiscais.toArray(), // ✅ chama Dexie no client
  },
  fiscal: {
    getApuracao: () => fetch("/api/mock/fiscal/apuracao/atual").then(r => r.json()), // ✅ Route Handler pra dados read-only
  },
};
```

---

## 14. Anexo: dados-semente da empresa demo

Hard-codar em `src/lib/db/seed.ts`:

```typescript
const EMPRESA_DEMO: Empresa = {
  id: "demo-001",
  cnpj: "12345678000199",
  razaoSocial: "FiscalAI Demo Tecnologia Ltda",
  nomeFantasia: "FiscalAI Demo",
  regime: "SIMPLES_NACIONAL",
  anexoSimples: "III",
  setor: "SERVICOS",
  cnae: "62.04-0/00", // consultoria em TI
  uf: "RS",
  municipio: "Porto Alegre",
  inscricaoEstadual: "ISENTO",
  inscricaoMunicipal: "987654321",
  faturamento12m: 850_000,
  socios: [
    { cpf: "12345678900", nome: "Maria Silva", participacao: 70, isAdministrador: true },
    { cpf: "98765432100", nome: "João Souza", participacao: 30, isAdministrador: false },
  ],
  certificadoA1: { nomeArquivo: "fiscalai-demo.pfx", validade: "2027-05-08", mock: true },
  bancosConectados: [
    { id: "b-1", banco: "Itaú", apelido: "Conta principal", saldo: 142_500, ultimaSync: new Date().toISOString() },
    { id: "b-2", banco: "Nubank PJ", apelido: "Reserva", saldo: 38_900, ultimaSync: new Date().toISOString() },
    { id: "b-3", banco: "Bradesco", apelido: "Movimento", saldo: 22_300, ultimaSync: new Date().toISOString() },
  ],
  modulosAtivos: ["fiscal", "notas", "contabil", "controles", "pessoal", "compliance", "agenda"],
  criadoEm: new Date(Date.now() - 14 * 30 * 24 * 60 * 60 * 1000).toISOString(),
};
```

---

## Fim do plano

> **Para o Claude Code:** comece pela Fase 0. Reporte ao final de cada fase com:
> - Lista de arquivos criados
> - Comandos rodados
> - Screenshots textuais (descrição) de cada tela entregue
> - Decisões tomadas que não estavam no plano (com justificativa)
>
> Em caso de bloqueio, **pare e pergunte**. Não improvise em ambiguidade fiscal — esses valores são mock, mas a UX precisa ser obsessivamente precisa.
