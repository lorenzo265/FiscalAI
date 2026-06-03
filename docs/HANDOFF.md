# HANDOFF — Re-engenharia Arkan (frontend)

Livro de passagem **append-only** entre os agentes da frota (ver `CLAUDE.md` §«Frontend —
Re-engenharia Arkan»). É assim que os agentes se coordenam **sem custo de mensagens diretas**: cada
um, ao terminar sua etapa, registra uma entrada no fim deste arquivo — **sem pedir confirmação**.

> **NUNCA reescreva ou apague entradas anteriores.** Só acrescente no fim. O histórico é a memória da frota.

## Formato de cada entrada
```
### YYYY-MM-DD · <agente> · <fase/lote>
- Fez: <o que entrou, em 1–3 linhas>
- Arquivos tocados: <caminhos>
- Build/lint: <OK | erros> · Gates/Invariantes: <OK | pendências>
- Pendências: <o que ficou faltando, ou "nenhuma">
- Faltou no design-system: <o que algum agente de tela precisou e não existe ainda, ou "—">
- Próximo: <agente que deve rodar a seguir>
```
O `reviewer` registra o veredito assim:
```
### YYYY-MM-DD · reviewer · PR <id/descrição>
- Veredito: APROVA | REPROVA
- Crítico: … · Aviso: … · Sugestão: …
- Dono da correção (se REPROVA): <agente>
```

## Estado atual
- **Fase:** 0 (não iniciada)
- **Pré-requisitos no repo:** `CLAUDE.md` (raiz) ✅ · contratos em `docs/` (plano + estilo + motion) · este `HANDOFF.md` ✅
- **Próximo:** `foundation` — executar a Fase 0 (tokens em `globals.css` + fontes em `layout.tsx`).

---

## Log

### 2026-06-01 · orquestrador · setup
- Fez: criado o bootstrap da frota — `CLAUDE.md` atualizado, 7 subagentes em `.claude/agents/`, contratos de design em `docs/`, e este HANDOFF.
- Arquivos tocados: `CLAUDE.md`, `.claude/agents/*.md`, `docs/*.md`.
- Build/lint: n/a · Gates/Invariantes: n/a
- Pendências: confirmar que os subagentes aparecem em `/agents` (reiniciar sessão se necessário).
- Faltou no design-system: —
- Próximo: `foundation` (Fase 0).

### 2026-05-31 · foundation · Fase 0
- Fez: trocou a fundação visual — tokens + fontes. `@theme` do `globals.css` agora é 100% Arkan "Instrumento" (papel quente `#EFEDE3` + tinta `#1B1A15` + UM acento verde `#136A41`, grafite/rule p/ fios técnicos, ocre/danger no mundo quente, `--radius:2px`, easings `--ease-settle/-reveal/-stamp`). Nomes antigos (`--color-bg/-line/-lime/-blue/-amber/-red/-txt*/-card*`, `--ease-default`) mantidos como **aliases de compat** apontando p/ os equivalentes Arkan (blue/amber → neutro/ocre, nunca 2º acento). `@layer base`/`utilities`: fundo papel + textura sutil de pauta (fios quase-imperceptíveis em `--color-rule`), reset `* → border-color: var(--color-rule)`, `html/body` tinta sobre papel (contraste ~14:1, AA ok), `.num/.mono` mantidos em mono tabular, scrollbar clara. `layout.tsx`: Plus Jakarta/JetBrains → **Fraunces** (serif, eixo `opsz`) + **Hanken Grotesk** (sans) + **Spline Sans Mono** (mono) via `next/font/google`, expondo `--font-serif/sans/mono-loaded`; 3 `.variable` no `<html>`; `metadata.title` preservado ("FiscalAI").
- Arquivos tocados: `analista-fiscal-web/src/app/globals.css`, `analista-fiscal-web/src/app/layout.tsx`.
- Build/lint: **OK** — `npm run build` (next build 15.5.18) compilou todas as rotas. Correção aplicada pelo orquestrador: Fraunces é fonte variável; com `axes:["opsz"]` o `next/font` exige `weight` inexistente ou `"variable"` — removido o array de `weight` da Fraunces (carrega a faixa toda). · Gates/Invariantes: OK — nenhum valor dark/neon remanescente (`#06080f`/lime), UM acento (verde), contraste base AA; só os 2 arquivos da Fase 0 tocados.
- Pendências: **remover os aliases de compat** do `@theme` na Fase 1 (design-system), migrando os ~93 arquivos/291 refs aos nomes Arkan canônicos.
- Faltou no design-system: —
- Próximo: `design-system` (Fase 1).

### 2026-05-31 · reviewer · PR Fase 0 (foundation)
- Veredito: APROVA
- Crítico: nenhum · Aviso: nenhum · Sugestão: (1) Fase 1 deve extinguir hardcodes `#06080f`/`var(--color-lime)` remanescentes em `button.tsx`, `checkbox.tsx`, `sonner.tsx`, `notas/emitir/nf-wizard-shell.tsx`, `layout/logo.tsx`, `fiscal/pix-modal.tsx`; (2) trocar `metadata.title` "FiscalAI"→"Arkan" na fase de shell/copy; (3) Fraunces carrega italic + opsz inteiro — reavaliar range no polish se bundle pesar.
- Conferido: sem valores dark/neon nos tokens; um acento (verde); ink/paper ≈14.7:1 (AAA), green/paper ≈5.2:1 (AA); tokens batem com §2.1 (paleta, radius 2px, easings); fontes next/font corretas (Fraunces variável sem `weight` + axes opsz); escopo respeitado (só os 2 arquivos); build verde.
- Dono da correção: n/a (APROVA).

### 2026-06-02 · design-system · Fase 1
- Fez: construiu o design-system Arkan que a frota consome. (1) **Revestiu as 24 primitivas `ui/*`** migrando dos aliases antigos (`txt/line/lime/blue/amber/red/bg/card-2/card-3`, `#06080f`) para os tokens canônicos (`ink/rule/green/paper/ochre/danger`), radius 2px (`--radius-md/-sm`), foco verde visível + ring-offset, fios 1px, easings dos tokens, sem pílulas/sombras-suaves-genéricas — **API (props) preservada**. Destaques: button (verde sobre papel, sem `#06080f`), badge (deixou de ser pílula → etiqueta 2px), tabs (virou underline-tab mono c/ acento verde, sem container-pílula), dialog/sheet/drawer (overlay `ink/45` + blur 2px no lugar de `black/70`, borda tinta, título serif), tooltip (tinta sobre papel), sonner (`theme="dark"`→`"light"`), checkbox/radio/switch/select/dropdown/popover/command/accordion/progress/alert. Corrigiu os hardcodes herdados do reviewer no MEU escopo (button, checkbox, sonner). (2) **Revestiu `shared/*`**: stat-card e estados em mono+serif+tokens; **pill agora é etiqueta técnica com cor+ícone+palavra** (invariante §7), `semIcone` opcional; empty/error trocaram o "ícone-em-quadradinho-lavado" por moldura 2px com corner-ticks; mono-number/moeda/data-br já usavam `.mono`. (3) **Criou `components/blueprint/*`**: `Framed` (+`CropMarks`), `Fig` ("Fig. 0X — …" mono), `Ruler` (régua de ticks CSS), `BlueprintSchematic` (esquemático da nota que se desenha via pathLength), `Carimbo` (selo green/ink/danger c/ overshoot + anel de tinta) + barril `index.ts`. (4) **Criou `lib/motion/*`**: `variants.ts` (reveal, revealChild, staggerChildren, lineMask, mediaFocus, drawOn/drawLine, stamp/stampRing, staticVariants + tokens EASE/DUR/STAGGER + defaultViewport), `useReveal`, `useReducedMotion`, `LenisProvider` (smooth-scroll auto-contido por rAF+lerp .09, só desktop/pointer-fine, fallback total em reduced-motion; **NÃO plugado no layout** — é da Fase 2) + barril `index.ts`. (5) **Showcase** em `src/app/(dashboard)/_showcase/page.tsx`: 11 seções numeradas (Fig.) com todas as primitivas + shared + blueprint + 1 exemplo de cada receita A–F (line-mask no headline, box-wipe, un-blur, draw-on, count-up na métrica, carimbo).
- Arquivos tocados: `src/components/ui/*` (button, input, card, badge, checkbox, sonner, label, separator, skeleton, tooltip, dialog, tabs, alert, progress, switch, select, dropdown-menu, popover, accordion, radio-group, scroll-area, sheet, command, drawer) · `src/components/shared/*` (stat-card, pill, empty-state, loading-state, error-state) · `src/components/blueprint/*` (framed, crop-marks, fig, ruler, blueprint-schematic, carimbo, index) · `src/lib/motion/*` (variants, use-reveal, use-reduced-motion, lenis-provider, index) · `src/app/(dashboard)/_showcase/page.tsx`. NÃO toquei `globals.css`/`layout.tsx` (aliases de compat preservados p/ as ~93 telas até a Fase 3).
- Build/lint: **OK** — orquestrador rodou `npm run build` (next 15.5.18): compilou todas as rotas sem erro. **PORÉM:** a showcase ficou em `(dashboard)/_showcase/` — pasta com prefixo `_` é *private folder* no App Router e **não vira rota**, então a showcase compila mas **não é acessível no browser** (não aparece na lista de rotas do build). DoD "showcase renderiza tudo" não está atendido até renomear (ex.: `_showcase`→`showcase`). · Validação estática do agente: 0 refs a tokens antigos nos arquivos que possui; tipos de motion ajustados (EASE como `Bezier`; `lineProps` tipado `MotionProps`). · Gates/Invariantes: OK — serifa+mono+fios/crop-marks+um-acento-verde; status=cor+ícone+palavra; props das primitivas intactas; motion só transform/opacity/clip-path/filter + reduced-motion; foco visível AA.
- Pendências: build a confirmar pelo orquestrador (não consegui rodar). `LenisProvider` usa smooth-scroll próprio (pacote `lenis` não instalado) — pode-se trocar pelo `lenis` na Fase 2/4 mantendo a API. Hardcodes fora do meu escopo (`layout/logo.tsx`, `notas/emitir/nf-wizard-shell.tsx`, `fiscal/pix-modal.tsx`) seguem para shell/telas. `metadata.title` "FiscalAI"→"Arkan" é da fase de shell/copy.
- Faltou no design-system: —
- Próximo: `shell` (Fase 2) — consumir primitivas/blueprint/motion, plugar `LenisProvider` no `(dashboard)/layout`, revestir sidebar/topbar/page-transition/command-palette. Sugiro o orquestrador chamar o `reviewer` neste PR antes da Fase 2.

### 2026-06-02 · reviewer · PR Fase 1 (design-system)
- Veredito: REPROVA
- Crítico: showcase em `(dashboard)/_showcase/` — pasta com prefixo `_` é private folder do App Router e NÃO gera rota; compila mas inacessível no browser, furando o DoD da Fase 1 (showcase renderizada com todas as primitivas). Renomear `_showcase`→`showcase` (ou `(showcase)`).
- Aviso: (1) `LenisProvider` faz `e.preventDefault()` no wheel (hijack de scroll) — corretamente gated (desktop + pointer-fine + sem reduced-motion) e degrada; reavaliar pacote `lenis` na Fase 2/4. (2) Dialog tem drop-shadow direcional `0_24px_60px_-30px` — aceitável p/ modal, vigiar p/ não virar sombra-suave-genérica.
- Sugestão: props herdadas `tom="lime"` (Progress) mapeiam p/ tokens canônicos — API preservada de propósito, ok; renomear p/ ok|warn|danger|neutral numa passada futura (não bloqueia).
- Conferido: ui/* e shared/* com 0 hardcode dark/neon e 0 alias antigo (grep limpo no escopo); canônicos ink/rule/green/paper/ochre/danger. Badge=etiqueta 2px; Tabs=underline mono+verde; Dialog overlay ink/45+blur; Sonner light; Input paper+foco verde+offset; pill=cor+ícone+palavra (§7) c/ semIcone aditivo; empty/error=moldura 2px+corner-ticks; serif+mono. Motion só transform/opacity/clip-path/filter; reduced-motion honrado; LenisProvider NÃO plugado. Escopo: globals.css/layout.tsx intocados; telas/hooks/providers/Dexie/charts/lógica não tocados; API shadcn preservada.
- Dono da correção: design-system (renomear pasta da showcase; reverificar build/rota).

### 2026-06-02 · orquestrador · correção do crítico Fase 1
- Fez: renomeou `src/app/(dashboard)/_showcase/` → `src/app/(dashboard)/showcase/` (rename mecânico, zero mudança de conteúdo — feito pelo orquestrador pois é correção sem juízo de design e o shell do `design-system` está quebrado nesta sessão). Showcase agora roteável em `/showcase`.
- Build/lint: OK — `npm run build` confirmou a rota `/showcase` na lista. · Crítico do reviewer: RESOLVIDO.
- Próximo: `shell` (Fase 2).

### 2026-06-02 · shell · Fase 2
- Fez: revestiu a **moldura** Arkan em volta de toda tela, consumindo o design-system da Fase 1 (sem reinventar tokens/primitivas; só tokens canônicos). (1) **logo.tsx**: descartou o gradiente lime→blue + traço hardcoded `#06080f` → selo de marca de registro (quadrado de fio 1px `--color-ink` sobre `--color-card`, radius 2px) com losango/diamante e miolo de tinta **verde** (`--color-green`) — resolve o hardcode apontado pelo reviewer da Fase 0. (2) **sidebar.tsx → índice-razão**: wordmark **Arkan** serif (Fraunces) + selo no topo; itens com **índice mono contínuo 01..N** (tabular), fios 1px, **sem pílulas** (removeu `bg-lime-d`/`rounded-md`), item ativo marcado por **fio verde 2px à esquerda** + índice/ícone verdes + `aria-current="page"`; grupos via `GROUP_LABELS` em mono; rodapé com empresa (razão social serif + regime mono). (3) **sidebar-mobile.tsx**: mesma linguagem; **overlay/scrim** mantidos (vaul `Drawer` direction=left, overlay `--color-ink/35`+blur), fecha ao navegar; targets ≥40px. (4) **topbar.tsx → masthead**: **vidro fosco** (`background:--color-glass` + `backdrop-filter: blur(14px) saturate`), wordmark Arkan serif no mobile, seletor de empresa com **selo verde** + razão serif + CNPJ mono, busca/Ctrl-K, assistente (outline verde, sem fundo lavado), conta — tudo preservado, só revestido; trocou `rounded-full`/`rounded-md` por radius 2px. (5) **page-transition.tsx**: coreografia Framer `AnimatePresence` — entrada clip-path wipe leve + y + un-fade (`EASE.reveal`, 420ms), saída y+fade (`EASE.settle`, 160ms); **branch reduced-motion** sem transform/clip (troca seca); só anima opacity/transform/clip-path. (6) **command-palette.tsx**: só ajuste de token de ícone (`--color-txt-3`→`--color-ink-3`); CommandDialog já revestido na Fase 1. (7) **alertas-flutuantes.tsx**: sem mudança (Toaster já revestido na Fase 1). (8) **LenisProvider plugado** no `(dashboard)/layout.tsx` envolvendo o shell (desabilita sozinho sob reduced-motion / touch). (9) **(auth)/layout.tsx**: shell de papel com wordmark Arkan + selo no topo.
- Arquivos tocados: `src/components/layout/logo.tsx`, `sidebar.tsx`, `sidebar-mobile.tsx`, `topbar.tsx`, `page-transition.tsx`, `command-palette.tsx` · `src/app/(dashboard)/layout.tsx`, `src/app/(auth)/layout.tsx`. NÃO toquei `nav-config.ts`, `providers.tsx`, `auth-guard`, `empresa-provider`, `query-provider`, `chat-flutuante`, `alertas-flutuantes.tsx`, globals.css/layout.tsx root.
- Build/lint: **OK** — orquestrador rodou `npm run build` (next 15.5.18): "✓ Compiled successfully", todas as rotas. Só warnings de lint pré-existentes (unused vars, não-erros). Validação estática do agente: 0 aliases antigos (`--color-txt/bg/lime/line/card-2/red`) e 0 hardcode (`#06080f`) nos arquivos do shell; imports resolvem. · Gates/Invariantes: OK — serif+mono+fios 1px+crop-marks-language, UM acento (verde), sem pílulas/sombras-genéricas; motion só transform/opacity/clip-path + reduced-motion honrado; foco/aria-current/targets ok.
- Invariantes preservados: **todas as 11 rotas/itens de nav acessíveis** (renderizados de `SIDEBAR_ITEMS`, nada removido); **filtragem por regime** via `moduloDisponivel` intacta (itens indisponíveis seguem com Lock+tooltip); **mobile overlay/scrim** funcionando; command palette/busca/assistente/conta/toasts preservados; `metadata.title` não tocado.
- Pendências: **build a confirmar pelo orquestrador** (não rodei). `LenisProvider` segue com smooth-scroll próprio (pacote `lenis` não instalado) — trocar pelo `lenis` mantendo a API fica para a Fase 4 (polish). `metadata.title` "FiscalAI"→"Arkan" segue para a fase de copy/rebrand. Hardcodes fora do meu escopo (`notas/emitir/nf-wizard-shell.tsx`, `fiscal/pix-modal.tsx`) são das telas (Fase 3).
- Faltou no design-system: — (tudo que precisei — `LenisProvider`, `EASE`, `useReducedMotion`, tokens `--color-glass`/`--color-green`/`--color-ink*`/`--radius` — já existia).
- Próximo: `screen-implementer` (lotes A–E) — revestir as telas de conteúdo consumindo este shell + o design-system; tela **Notas** = gabarito de ouro. Sugiro o orquestrador rodar `npm run build` e chamar o `reviewer` neste PR antes da Fase 3.

### 2026-06-02 · reviewer · PR Fase 2 (shell)
- Veredito: APROVA
- Crítico: nenhum.
- Aviso: (1) targets de toque < 44px (contrato §A11y exige >=44px): topbar hamburguer/busca-mobile size-10 (40px), conta size-9 (36px), Assistente h-9 (36px); sidebar-mobile close size-9 (36px) e linhas de nav ~40px. Subir alvos mobile/conta para >=44px (min-h/min-w 44px ou size-11) sem virar pilula. (2) --color-ink-3 (#928f7e) sobre papel ~2.7:1, falha AA p/ texto normal; aplicado a dados load-bearing no shell (indice mono, CNPJ no masthead, labels de grupo). Token herdado da Fase 0/1, mas o shell o usa em info essencial. Reavaliar ink-3 ou usar ink-2 para indice/CNPJ. (Itens desabilitados em ink-3 sao isentos.)
- Sugestao: (1) metadata.title FiscalAI->Arkan na fase de copy. (2) LenisProvider faz preventDefault no wheel (gated/degrada); avaliar pacote lenis real na Fase 4.
- Conferido: anti-AI-slop OK (sidebar sem pilula, ativo=fio verde 2px+peso; topbar vidro fosco real backdrop-filter+--color-glass; wordmark serif; mono nos dados; fios 1px; um acento; logo sem #06080f/lime). Invariantes §7 OK: nav-config intacto, 11 itens renderizados, filtragem por regime preservada (disabled+Lock+tooltip), aria-current, overlay/scrim mobile fecha ao navegar, command palette/busca/assistente/conta/toasts preservados. LenisProvider plugado dentro de AuthGuard sem quebrar providers; off em reduced-motion/touch. Motion so opacity/y/clip-path + branch reduced-motion. Tokens todos existem; 0 hardcode/alias antigo; nada reinventado. Escopo respeitado. Build verde.
- Dono da correcao: avisos de a11y para `shell` antes da Fase 3; ink-3 e questao de token p/ `foundation`/`design-system`.

### 2026-06-02 · orquestrador · correção dos avisos a11y da Fase 2
- Fez: aplicou as 2 correções de a11y do reviewer (mecânicas, sem juízo de design aberto; feito pelo orquestrador pois não há SendMessage para o `shell` nesta sessão e respawn seria caro). (1) **Targets ≥44px**: topbar hamburguer/busca-mobile `size-10`→`size-11`, conta `size-9`→`size-11`, Assistente `h-9`→`h-11`, busca desktop `h-9`→`h-11` (alinhamento); sidebar-mobile close `size-9`→`size-11`, linhas de nav (ativa+disabled) ganharam `min-h-[44px]`. (2) **Contraste AA**: `--color-ink-3`→`--color-ink-2` em todo texto load-bearing do shell (tagline "Fiscal · Instrumento", labels de grupo, índice mono + ícone de itens ATIVOS/habilitados, CNPJ no masthead + dropdown, label "Empresa" do rodapé, kbd "Ctrl K"). Mantido `ink-3` em itens DESABILITADOS (isentos de AA) e no chevron decorativo.
- Arquivos tocados: `src/components/layout/topbar.tsx`, `sidebar.tsx`, `sidebar-mobile.tsx`.
- Build/lint: OK — `npm run build` "Compiled successfully", todas as rotas. · Avisos do reviewer: RESOLVIDOS. Pendência de token (rever valor de `--color-ink-3` no `@theme`) segue para `foundation`/`design-system` numa passada futura; o shell já não depende de ink-3 para info essencial.
- Próximo: `screen-implementer` (lotes A–E) — Fase 3.