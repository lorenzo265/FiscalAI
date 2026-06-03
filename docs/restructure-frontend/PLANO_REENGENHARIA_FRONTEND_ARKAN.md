# Plano de Re-engenharia do Frontend — Arkan ("Ferramenta de Precisão")

**Produto:** Arkan (app) · Arkan Fiscal Technologies
**Energia-alvo:** *uma ferramenta de precisão na mão de um artesão com anos de experiência.* Séria,
exata, calma, lindamente desenhada — um cartório do futuro, não "mais um app de IA".
**Documentos-contrato (linguagem):** `arkan-motion-extraction.md` (animação) e
`arkan-visual-style-merge.md` (estilo). Este plano os operacionaliza sobre o código real.

---

## 0. Princípio diretor

**Re-vestir, não re-arquitetar.** A auditoria do projeto real (`analista-fiscal-web`) mostrou uma base
madura e bem estruturada. A arquitetura, as funções, os dados e os fluxos **ficam**. Trocamos a *pele*
— e a pele é dirigida por tokens, então a troca é majoritariamente **central**, não 100 edições manuais.

> Regra inegociável herdada da skill: **detalhe no craft, calma no conteúdo.** E os *gates anti-AI-slop*
> (seção 8) valem para todo PR. Nenhuma função pode ser perdida no caminho (seção 7).

---

## 1. Auditoria do estado atual (snapshot para futuras checagens)

### Stack real
Next.js 15 (App Router) · React 19 · TypeScript · **Tailwind v4 (CSS-first, sem `tailwind.config`)** ·
**shadcn/ui** (Radix + cva + clsx + tailwind-merge) · TanStack Query + Table · **Framer Motion 11 (já
instalado)** · Recharts · React Hook Form + Zod · Zustand · nuqs · Dexie (persistência local/mock) ·
faker (dados) · jsPDF/qrcode/jsbarcode (DANFE) · sonner · vaul · cmdk.

### Tamanho
~45 rotas · 100 componentes · 12 hooks · 8 rotas de API mock · ~62 arquivos em `lib`.

### Mapa de rotas (o que existe e precisa ser revestido)
```
(auth)        login · onboarding
(dashboard)   home
              fiscal (· guias · simulador · reforma-tributaria)
              notas (· entrada · saida/nova · [chave])
              agenda
              compliance (· certidoes · intimacoes · parcelamentos)
              controles (· bancos[/id, /conectar] · pagar · receber)
              contabil (· lancamentos · razao/[conta] · encerramento)
              pessoal (· folha[/ano/mes] · funcionarios[/novo] · esocial)
              relatorios (· dre · dfc · balanco · indicadores)
              assistente
              configuracoes (· empresa · certificado · integracoes · usuarios)
```

### Domínios de componentes
`ui` (primitivas shadcn) · `shared` (stat-card, pill, mono-number, moeda, data-br, empty/loading/error
states) · `layout` (sidebar, topbar, page-transition, command-palette, providers, auth-guard…) ·
`home · fiscal · notas · agenda · compliance · controles · contabil · pessoal · relatorios ·
assistente · onboarding · configuracoes`.

### O ponto de alavancagem (a descoberta central)
O tema vive em `src/app/globals.css` num bloco **`@theme`** (Tailwind v4). As primitivas referenciam
tokens direto (ex.: `bg-[var(--color-lime)]`). **Trocar os tokens + revestir as primitivas propaga
por todo o app.** A paleta atual está marcada no código como *"copiada do fiscalai_v4.html"* — é
exatamente o dark/neon que estamos descartando (`--color-bg:#06080f`, `--color-lime:#a3ff6b`,
fontes Plus Jakarta + JetBrains Mono).

### Veredito
**Manter:** arquitetura, rotas, hooks, dados/mock, lógica fiscal, shadcn como base.
**Trocar (visual):** tokens, fontes, estilo das primitivas e dos `shared`, shell, e adicionar duas
camadas novas — **blueprint** (a personalidade técnica) e **motion** (a experiência premium).

---

## 2. Sistema de design alvo — Arkan "Instrumento"

### 2.1 Tokens (substituem o `@theme` atual)
Papel quente + tinta + **um verde** (marca = saúde fiscal), grafite para linhas técnicas, cantos quase
retos, fios 1px, elevação mínima. Mapear para `@theme` do Tailwind v4:

```
--font-serif: "Fraunces"            /* títulos — caráter editorial */
--font-sans:  "Hanken Grotesk"      /* UI/corpo — legível */
--font-mono:  "Spline Sans Mono"    /* dados, códigos, rótulos técnicos */

--color-paper:#EFEDE3  --color-paper-2:#E7E4D7  --color-card:#F7F5EE  --color-glass:rgba(239,237,227,.72)
--color-ink:#1B1A15    --color-ink-2:#59574B     --color-ink-3:#928F7E  --color-graphite:#A7A493
--color-rule:#D4D0C0   --color-rule-2:#C1BCA9
--color-green:#136A41  --color-green-deep:#0C4327 --color-green-bright:#1B8A55 --color-green-wash:#DDE8DE
--color-ochre:#A8650F  (atenção)    --color-danger:#B23A33 (erro, dentro do mundo quente)
--radius-md:2px --radius-sm:2px      /* precisão, não fofura */
--ease-settle:cubic-bezier(.16,1,.3,1)  --ease-reveal:cubic-bezier(.62,.05,.01,.99)  --ease-stamp:cubic-bezier(.34,1.56,.4,1)
```
Regras: texto AA · status sempre **cor + ícone + palavra** · **um** acento (verde) · sem dark/neon.
Dark mode é fase posterior (re-derivar, não inverter).

### 2.2 Linguagem de componente (a "ferramenta de precisão")
- **Painel `Framed`**: borda 1px tinta + **crop marks** nos cantos (registro técnico).
- **`Fig`**: rótulo mono "Fig. 0X — …" que numera seções como documento técnico.
- **`Ruler`**: régua de medição com ticks (divisor técnico).
- **`BlueprintSchematic`**: desenho de engenharia (linha grafite) que **se desenha** — começa pela
  nota; vira uma família de esquemas por feature.
- **`Carimbo`**: selo que bate no parecer/estado resolvido (assinatura).
- **Dados em mono tabular**; títulos em serifa; rótulos técnicos em mono caixa-alta.

### 2.3 Motion (ver `arkan-motion-extraction.md`)
Lenis (scroll suave) + Framer Motion (já instalado) com `variants`: line-mask no headline, reveal de
box (clip-wipe + filhos escalonados), un-blur + scale-into-focus em mídia, draw-on de fios/blueprint,
count-up, carimbo. Tudo com fallback `prefers-reduced-motion` e só `transform/opacity/clip-path/filter`.

---

## 3. Camadas-contrato (construídas primeiro, consumidas por todos)

Estas peças são a fundação compartilhada. Devem ser feitas **antes** das telas e **não** podem ser
divergidas por agentes de domínio:

| Camada | Arquivo(s) | Conteúdo |
|---|---|---|
| **Tokens** | `src/app/globals.css` (`@theme`) | a paleta/tipos/easings da seção 2.1 |
| **Fontes** | `src/app/layout.tsx` | Fraunces + Hanken Grotesk + Spline Sans Mono via `next/font/google` |
| **Primitivas** | `src/components/ui/*` | cva revestida para a linguagem Arkan (botão, card, input, tabs, dialog, badge…) |
| **Shared** | `src/components/shared/*` | stat-card, pill, mono-number, moeda, states — revestidos |
| **Blueprint** | `src/components/blueprint/*` (novo) | `Framed`, `CropMarks`, `Fig`, `Ruler`, `BlueprintSchematic`, `Carimbo` |
| **Motion** | `src/lib/motion/*` (novo) | `variants.ts` (reveal/lineMask/drawOn/stamp), `LenisProvider`, `useReveal`, `useReducedMotion` |

> Os dois markdowns de extração (motion + estilo) são o **contrato de linguagem**; este quadro é o
> **contrato de código**. Todo agente de domínio importa daqui e não reinventa.

---

## 4. Estrutura de pastas (adições)
```
src/
  app/globals.css            ← tokens novos
  app/layout.tsx             ← fontes novas
  components/
    ui/                      ← revestidos
    shared/                  ← revestidos
    blueprint/               ← NOVO (Framed, CropMarks, Fig, Ruler, BlueprintSchematic, Carimbo)
    layout/                  ← shell revestido (sidebar, topbar, page-transition…)
  lib/
    motion/                  ← NOVO (variants, LenisProvider, hooks)
    design/tokens.ts         ← NOVO (opcional: espelho TS dos tokens p/ uso em JS)
```

---

## 5. Roadmap por fases (com paralelização)

### Fase 0 — Fundação de tokens *(serial, bloqueia tudo · 1 agente)*
Trocar `@theme` (2.1) + fontes (2.2) + base do `globals.css` (papel, textura de pauta, scrollbar
clara). Resultado: o app inteiro "vira" papel/tinta/verde de imediato, ainda que cru. **DoD:** app
compila, nenhum `#06080f`/`lime` remanescente nos tokens, contraste AA no texto base.

### Fase 1 — Primitivas + Blueprint + Motion *(serial curto · "design-system agent")*
Revestir `ui/*` e `shared/*`; criar `components/blueprint/*` e `lib/motion/*`. **DoD:** uma
página de showcase com todas as primitivas no novo estilo; `Framed/Fig/Ruler/Carimbo/BlueprintSchematic`
prontos; variants de motion documentadas; reduced-motion ok.

### Fase 2 — Shell *(serial curto · "shell agent")*
`layout/sidebar` → índice-razão (01–06 mono, fios, sem pílulas), `topbar` → masthead vidro fosco,
`page-transition` (Framer), `command-palette`, `LenisProvider` no `(dashboard)/layout`. **DoD:**
navegar entre telas com transição suave; shell idêntico à PoC.

### Fase 3 — Telas por domínio *(PARALELO · vários agentes)*
Cada agente possui um domínio, consome as camadas-contrato, preserva funções (seção 7). Sugestão de
lotes balanceados:
- **A — Início + Fiscal** (home, fiscal, guias, simulador, reforma-tributaria) — inclui fiscal-health-score, charts Recharts re-tematizados.
- **B — Notas** (lista, entrada, saida/nova wizard, [chave]/DANFE) — a "Analisar Nota" da PoC é o gabarito de ouro aqui.
- **C — Controles + Contábil** (bancos, pagar/receber, lançamentos, razão, encerramento).
- **D — Pessoal + Relatórios** (folha, funcionários, esocial, dre/dfc/balanço/indicadores).
- **E — Compliance + Agenda + Configurações + Onboarding + Assistente**.
**DoD por tela:** passa nos gates (seção 8); funções intactas; reveals/estados/empty/error no estilo.

### Fase 4 — Acabamento premium *(serial · "polish agent")*
Passada de motion (pinned/parallax sutil onde agrega, transições entre telas), a11y/perf (60fps mobile,
reduced-motion auditado), **dark mode** re-derivado, microilustrações blueprint em empty states,
ícones/esquemas próprios por feature. **DoD:** Lighthouse a11y ≥ 95; nenhuma regressão de função.

---

## 6. Frota de agentes (Claude Code)

| Agente | Dono de | Lê | Não pode |
|---|---|---|---|
| **Foundation** | Fase 0 (tokens, fontes) | os 2 contratos | tocar em telas |
| **Design-System** | Fase 1 (primitivas, blueprint, motion lib) | os 2 contratos | mudar funções |
| **Shell** | Fase 2 (layout) | F1 + contratos | mudar rotas/nav config além do visual |
| **Domínio A–E** | Fase 3 (telas) | F0–F2 + contratos | reinventar tokens/primitivas; alterar lógica/hooks/dados |
| **Polish/QA** | Fase 4 + gates | tudo | introduzir slop |

**Ordem/dependências:** F0 → F1 → F2 → (A–E em paralelo) → F4. F3 só começa após F1 estável (senão os
agentes de domínio retrabalham). Cada agente trabalha em branch própria; PRs passam pelos gates.

---

## 7. Invariantes de função (não quebrar ao revestir)
- Toda rota e item de navegação continua acessível; nada some.
- Hooks (`use-*`), providers (Query/Empresa/Auth), Dexie/mock e lógica fiscal **inalterados**.
- Wizards (onboarding, emissão de NF, admissão) mantêm passos e validação (RHF+Zod).
- DANFE/PDF/QR/barcode seguem funcionando.
- Charts (Recharts) re-tematizados, **mesmos dados**.
- Status sempre **cor + ícone + palavra**; nunca expor CFOP/CST/NCM crus ao dono de PME — traduzir.
- Command palette, toasts (sonner), drawers (vaul), tooltips — preservados, só revestidos.

## 8. Gates de qualidade (todo PR)
**Anti-AI-slop (da skill):** sem coluna central + cards arredondados flutuando; sem sombras suaves por
toda parte; sem pílulas/ícone-em-quadradinho-lavado; tipo com caráter (serifa display + mono dados);
estrutura com fios/crop marks; **um** acento. Se bater nos "tells", reprova.
**Função:** a tela faz tudo que fazia antes (checklist da seção 7).
**Motion:** só transform/opacity/clip-path/filter; `prefers-reduced-motion` honrado; 60fps mobile.
**A11y:** contraste AA; foco visível; navegável por teclado; targets ≥ 44px.

## 9. Riscos & mitigação
- **Tailwind v4 `@theme`**: mudanças de token são globais — testar em uma tela "canário" (Notas) antes
  de liberar F3. *Mitig.:* Fase 0 isolada + página de showcase na F1.
- **Deriva de primitivas**: agentes de domínio "customizando" botões/cards. *Mitig.:* contrato de código
  (seção 3) + gate de revisão; domínios importam, não reescrevem.
- **Motion x perf mobile**: *Mitig.:* orçamento de motion (1 entrada + 1 signature por tela), Lenis só
  desktop/sem reduced-motion, lazy nos charts.
- **Escopo (45 rotas)**: *Mitig.:* paralelização por lote + a PoC "Analisar Nota" como gabarito.

## 10. Definition of Done (global)
Todas as rotas no estilo "Instrumento", funções 100% preservadas, motion premium com fallback,
a11y ≥ 95, dark mode re-derivado, e os componentes `blueprint`/`motion` documentados para evolução.

---

### Próximos passos imediatos
1. Anexar **este plano + o zip + os 2 contratos** ao conhecimento do projeto (não consigo escrever no
   `/mnt/project`; os arquivos estão nos *outputs* prontos pra você subir).
2. Quando aprovar, eu detalho a **Fase 0 + Fase 1 como specs prontas de Claude Code** (diff do
   `globals.css`, a `layout.tsx` com as fontes, e o código de cada componente `blueprint/` e do
   `lib/motion/`), pra você abrir e distribuir entre os agentes.
