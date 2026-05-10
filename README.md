# FiscalAI

Plataforma de análise fiscal e contábil mockada para apresentação. Demo de produto end-to-end: onboarding, dashboard de saúde fiscal, módulos de notas, contábil, controles, pessoal, relatórios, compliance, agenda e assistente IA.

## Estrutura

```
.
├── analista-fiscal-web/   ← App Next.js 15 (App Router) — código do produto
└── docs/
    └── Plano.md           ← Plano de implementação (13 fases)
```

## Como rodar

```bash
cd analista-fiscal-web
pnpm install
pnpm dev
```

App sobe em http://localhost:3000.

## Stack

Next.js 15 · React 19 · TypeScript strict · Tailwind v4 · TanStack Query/Table · Zustand · React Hook Form + Zod · Recharts · Dexie · shadcn-style primitives. Detalhes completos em [`docs/Plano.md`](./docs/Plano.md).

## Status

Todas as 13 fases do Plano implementadas. Build de produção passa, Lighthouse desktop **96-99 Performance** nas rotas autenticadas. Autenticação e dados são todos mockados (sem backend real).
