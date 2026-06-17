# Arkan Claro — Identidade v2 (Instrumento × Apple)
## 2026-06-11 | Modo: [IDENTITY] | Contrato de design do workstream Experiência (Plano Production-Ready §4)

**Tese nomeada:** *"O instrumento de precisão, agora leve na mão."*

A v1 ("Instrumento") provou o DNA: precisão, papel + tinta, UM verde, mono nos dados, Carimbo como rito. A v2 mantém esse DNA e troca a **densidade técnica** (blueprint em toda moldura, fios por toda parte, serifa em todo título) por **clareza espacial e fluidez** — o que se entende à primeira vista, o que parece inevitável. Apple aqui não é estética emprestada; é disciplina: menos elementos, mais respiro, hierarquia por escala e peso, movimento que explica.

**Por que é barato:** o tema é 100% dirigido por tokens (`@theme` no `globals.css`). A v2 é uma re-calibração de tokens + uma passada nas 24 primitivas. Telas, hooks, lógica e funções não mudam (invariantes §7 do CLAUDE.md intactos).

---

## §1 — O que fica e o que muda

| Fica (DNA, inegociável) | Muda (calibração Apple) |
|---|---|
| UM acento verde = saúde fiscal | Papel 1 passo mais claro; superfícies branco-quente planas |
| Mono tabular em TODO dado/valor | Número-herói ganha palco: mono light em 56–72px (o "valor" é o protagonista da tela) |
| Status = cor + ícone + palavra | Fios 1px recuam: só onde estruturam dados (tabelas, divisores); painel comum perde a moldura técnica |
| Carimbo como rito pós-ação | Crop marks/Fig./régua decorativa saem do painel comum → viram **assinatura rara** (tela de detalhe, PDF, confirmações) |
| Tradução fiscal §7, urgência 3 níveis | Serifa Fraunces recua para momentos-marca: título de página, wordmark, Carimbo. UI corre em Hanken |
| Motion só transform/opacity/clip/filter + reduced-motion | Motion vira protagonista: springs, transições compartilhadas, count-up — a fluidez É o "Apple feel" |
| Radius pequeno em controles; nunca pílula | Radius cresce em superfícies grandes (10px painel, 16px sheet) — profundidade por material translúcido, não sombra |

---

## §2 — Tokens v2 (contrato; substitui valores no `@theme`, nomes mantidos)

```css
@theme {
  /* Superfícies — papel mais claro, painel branco-quente plano */
  --color-paper:  #F7F5EF;   /* era #EFEDE3 */
  --color-paper-2:#F1EEE4;   /* wells, hover de linha */
  --color-card:   #FDFCF8;   /* painel: plano, sem sombra */
  --color-glass:  rgba(252,251,246,.72); /* chrome translúcido (masthead, tab bar) */

  /* Tinta */
  --color-ink:   #1C1B16;
  --color-ink-2: #5A5749;    /* secundário, AA sobre paper e card */
  --color-ink-3: #908C7B;    /* APENAS decorativo/disabled — nunca dado */

  /* Fios — mais claros: estrutura recua, conteúdo avança */
  --color-rule:  #E6E3D6;
  --color-rule-2:#D5D1C1;

  /* Acento único */
  --color-green:      #0E6B43;
  --color-green-deep: #0A4E31;
  --color-green-wash: #E9F2EC;

  /* Semânticos (mundo quente) */
  --color-ochre: #96660D;  --color-ochre-wash: #F7EEDB;
  --color-danger:#B3382E;  --color-danger-wash:#F9E9E6;

  /* Geometria */
  --radius-sm: 6px;   /* inputs, badges, pills */
  --radius-md: 10px;  /* painéis, botões */
  --radius-lg: 16px;  /* sheets, modais, tab bar — NUNCA em botão (pílula) */

  /* Motion */
  --ease-settle: cubic-bezier(.2,.8,.2,1);
  --ease-reveal: cubic-bezier(.16,1,.3,1);
  --dur-fast: 160ms; --dur-base: 320ms; --dur-page: 420ms;
}
```

Springs (Framer Motion, fora do CSS): `press = {stiffness:420, damping:30}` · `surface = {stiffness:260, damping:32}` · `stamp` mantém o overshoot da v1. Dark mode: re-derivar pelo mesmo método da Fase 4 v1 (não inverter), partindo destes valores.

**Tipografia (famílias mantidas, papéis recalibrados):**

| Papel | Fonte | Tamanho/peso | Uso |
|---|---|---|---|
| Display (valor-herói) | Spline Sans Mono | 56–72px / 300, tabular, tracking −2% | O número que responde a pergunta da tela. 1 por tela. |
| Título de página | Fraunces (opsz alto) | 28–32px / 560 | Só no topo da página e no Carimbo |
| Seção / card label | Hanken Grotesk | 13px / 600, caps largas +6% | Substitui o rótulo mono "Fig." do painel comum |
| Corpo / UI | Hanken Grotesk | 15px / 450 | Tudo |
| Dado em tabela/linha | Spline Sans Mono | 13–14px / 400, tabular | Valores, datas, CNPJ, protocolos |

**Espaço (a lei do respiro):** base 4px; escala 4·8·12·16·24·32·48·64·96. Mínimo 24px entre blocos, 48–64px entre seções. **Máximo 3 blocos acima da dobra** em qualquer tela. Se uma tela precisa de mais, ela está tentando responder mais de uma pergunta — dividir.

---

## §3 — Linguagem de componente (delta sobre a v1)

- **Painel:** `card` branco-quente, borda 1px `rule`, radius 10, **sem sombra e sem crop marks**. O painel v1 (`Framed` + marks + Fig.) vira `Framed variant="technical"` — usado SÓ em telas-assinatura (detalhe da nota, confirmações, PDF).
- **Botão primário:** verde sólido, radius 10, altura 44px (mobile-first resolve o aviso de a11y da Fase 2), press scale .97 com spring; ícone opcional à esquerda. Um por tela.
- **Listas/tabelas:** fio horizontal 1px apenas; hover = fundo `paper-2` (sem borda nova); linha inteira clicável com chevron; no mobile a tabela vira card (auditoria UX §10).
- **Pill de status:** mantém cor+ícone+palavra; fundo wash, radius 6 — sem mudança estrutural.
- **Carimbo:** intocado. É a assinatura nº 1 da marca.
- **Régua de limites (`Ruler` evoluída):** vira componente-assinatura nº 2 — régua horizontal com ticks mono, preenchimento verde do progresso, marcador de projeção ("no seu ritmo: outubro"). Usada nos monitores de limite (Plano §5, ferramenta 09).
- **Navegação mobile: tab bar inferior** (novo) — 4 destinos + "mais": Visão geral · Notas · Pagar · Agenda · Mais. Vidro translúcido (`glass` + blur), radius 16 flutuando 8px da base, ícone+palavra sempre. No desktop a sidebar v1 permanece, com fios mais leves e índices mono mantidos (identidade).
- **Masthead:** já é vidro fosco na v1 — mantém, com fios reduzidos.
- **Ícones:** Lucide stroke 1.75, sem tile/wash atrás. Nunca emoji.

---

## §4 — Motion v2 (onde mora o "Apple feel")

Orçamento por tela mantido: **1 entrada + 1 assinatura**. Tudo honra `prefers-reduced-motion` (troca seca via `staticVariants`).

| Momento | Receita | Spec |
|---|---|---|
| Transição de página | Shared-axis: saída fade+y−8 (160ms settle), entrada fade+y+12 (420ms reveal) | já existe; recalibrar distância/curva |
| Número-herói | Count-up 600ms ease-out, 1× por valor por sessão; tabular evita jitter | novo hook `useCountUp` em `lib/motion` |
| Press de botão/linha | scale .97 spring(420,30) | global nas primitivas |
| Surface (modal/sheet/tab bar) | y+24 → 0 com spring(260,32), overlay ink/35 + blur 2px | recalibra dialog/sheet v1 |
| Carimbo | overshoot v1 intocado | — |
| Régua de limites | preenchimento desenha da esquerda (scaleX, 800ms reveal) + tick de projeção pulsa 1× | assinatura da home |
| Scroll | Lenis (desktop, pointer-fine) mantido | — |

---

## §5 — Gates anti-slop v2 (atualização do checklist do reviewer)

A direção Apple **não** é licença para virar genérico. REPROVA se: tudo-sans sem a serifa nos momentos-marca · dado em fonte proporcional · segundo acento de cor · botão-pílula ou radius 16 em controle · sombra suave difusa como profundidade (profundidade aqui = material translúcido ou plano) · ícone em quadradinho lavado · saudação "Olá, fulano 👋" · mais de 3 blocos acima da dobra · painel comum com crop marks (inflação da assinatura). APROVA se: 1 pergunta respondida em 5s · 1 número-herói · 1 ação primária · respiro ≥ escala · mono em todo dado · verde só onde significa saúde/ação.

---

## §6 — Brand pack (entregáveis de marca, Sprint 8)

1. **Logo:** evolução do selo v1 (quadrado de fio + losango) para versão simplificada que funcione a 16px (favicon) e 1024px (loja) — 1 cor (verde) + versão tinta. Wordmark "Arkan" em Fraunces, espaçamento fixado.
2. **Brand book** (`docs/arkan-brand-book.md` + PDF): tese, tokens, type, dos/don'ts, voz e tom (calmo, exato, sem jargão — espelha a tradução §7), exemplos de aplicação.
3. **Landing page:** hero = o produto real (screenshot vivo da home com número-herói), não ilustração abstrata; uma frase: *"Você sabe o que está acontecendo no seu fiscal."*; CTA único (trial/waitlist); seção "como funciona" em 3 passos; prova social dos contadores do beta.
4. **Templates:** e-mail transacional (mesmo type system), social (anúncio de lançamento), DANFSE/PDF re-tematizados (onde o `Framed technical` + crop marks vivem para sempre).

---

## §7 — Plano de execução do design (fases D0–D6, encaixe nas sprints do Plano)

| Fase | Sprint | Entregável | DoD | Dono |
|---|---|---|---|---|
| D0 Extract | S3 sem.1 | Teardown de 3 referências (método `extraction-laws`): 1 Apple (HIG/apps nativos), 1 ferramenta premium clara, 1 banking app BR premium → leis sintetizadas | nota em `docs/` com tokens/princípios extraídos, zero cópia | frontend-design-architect |
| D1 Tokens | S3 sem.2 | `@theme` v2 (valores §2) + dark re-derivado + showcase `/showcase` re-renderizada | gate §5 verde no showcase; AA nos 2 temas; build verde | foundation |
| D2 Primitivas | S4 sem.1 | Passada nas 24 `ui/*` + `shared/*` (deltas §3) + `useCountUp` + tab bar mobile no shell | API preservada; invariantes §7; Lighthouse a11y ≥95 no showcase | design-system + shell |
| D3 Gabarito | S4 sem.2 | Tela Notas re-calibrada v2 (gabarito de ouro, de novo) | reviewer fresco aprova gates v2; "5 segundos" testado | screen-implementer |
| D4 Lotes | S5–S6 | Lotes A/C/D/E imitam o gabarito; home v2 com número-herói + régua | gate §5 por tela; zero regressão de função | screen-implementer ×4 |
| D5 Marca | S8 | Brand pack completo (§6) + landing no ar | landing publicada com waitlist; brand book no vault | frontend-design-architect |
| D6 Polish | S11 | Motion final (springs calibrados em device real), dark validado por humano, Lighthouse ≥95 geral | P3 do Plano verde | motion-polish |

**Processo:** mesmo protocolo da v1 que funcionou — HANDOFF append-only, reviewer de contexto fresco em todo PR, screen-implementers no tree principal (lição da Fase 3), gabarito antes dos lotes.

---

## §8 — O que este documento NÃO autoriza

Mudar função, rota, hook, wizard, lógica fiscal ou contrato de API (invariantes do CLAUDE.md). Criar segundo acento. Remover a tradução §7. Reintroduzir dark/neon. Animar width/height/top/left. Expor sigla sem tradução. Tutorial/tour como muleta — se a tela precisa de tour, a tela está errada.
