# Proposta de Design — Arkan

**Arkan Fiscal Technologies** · Sistema de design "O Instrumento" · v1
*Documento de proposta. Consolida a direção; os contratos de execução são `arkan-visual-style-merge.md`
(estilo) e `arkan-motion-extraction.md` (motion).*

---

## 1. Em uma frase

> Um **instrumento de precisão na mão de um artesão com anos de experiência.** Sério, exato, calmo e
> lindamente desenhado — um cartório do futuro, não "mais um app de IA".

## 2. Por que mudar

O frontend nasceu com uma estética de **ferramenta de dev/IA**: fundo quase preto, neon, logo
hexágono, rótulos em mono. Isso comunica "produto técnico para engenheiros" — o oposto do que o nosso
público lê como confiável.

**Público:** o **dono de PME** (ex.: distribuidora, restaurante) — não é contador, não é técnico, paga
um contador e não entende os próprios números. Disso decorre tudo: **simplicidade e compreensão
imediata vencem**, sem informação desnecessária, com tom de **confiança e calma** — não de gadget.

## 3. O conceito — "O Instrumento"

A identidade não é decorativa: ela **nasce do que o produto faz**. O domínio é documento fiscal —
então a linguagem vem daí: papel, tinta, aferição, registro, carimbo. O resultado é uma ferramenta
que parece um **instrumento de medição** lindamente feito: estrutura visível, precisão, e o gesto de
**conferir-e-marcar** virando assinatura.

Fundimos o melhor de duas referências de altíssimo craft (princípios, nunca cópia):
- **Floema** (estúdio Büro): calor de papel, confiança editorial, e o **desenho técnico em linha** —
  a ponte para o "tecnológico" sem ser frio.
- **Fluid Glass** (estúdio Exo Ape): clareza cinematográfica, ar premium, *quiet luxury*.

> **Tese:** *um instrumento fiscal desenhado como um blueprint de engenharia, sobre papel quente, com
> a clareza cinematográfica do vidro.* — entrega personalidade + ar profissional + camada tecnológica.

## 4. Princípios

1. **Detalhe no craft, calma no conteúdo.** Capricho extremo em *como* as coisas se movem e se
   compõem; conteúdo enxuto na tela. Animação sempre a serviço da compreensão.
2. **Simples ≠ genérico.** Fugimos dos "tells" de IA (coluna central + cards arredondados flutuando,
   pílulas, sombras suaves por toda parte, tudo sans). Distinção vem de **tipo + estrutura + um acento
   + uma assinatura**.
3. **Status sobre números.** Um veredito claro → sinais → detalhe sob demanda. Nunca jargão (CFOP/CST)
   na cara do dono de PME — traduzir para português claro.
4. **Confiança e acessibilidade.** Status sempre cor + ícone + palavra; contraste AA; respeito a
   `prefers-reduced-motion`; 60fps em mobile.

## 5. Sistema de identidade

### A marca — "Register-Mark A"
Um "A" desenhado como instrumento de aferição: **ápice chanfrado** (engenharia, não caligrafia) e a
**travessa virando um tick de medição** que ultrapassa a perna — o gesto de quem confere e marca.
Conversa direto com os crop marks, a régua e o carimbo do app.
- Lockups: horizontal (principal), reversa sobre verde, selo monocromático.
- **Arquivo Figma editável** (marca, lockups, estilos de cor, tipografia):
  https://www.figma.com/design/xKT3B3B5bGSd7n4ysYa2hd

### Cor — tinta · papel · um verde
| Papel | Tinta | Verde (marca) | Grafite | Ocre | Vermelho |
|---|---|---|---|---|---|
| #EFEDE3 | #1B1A15 | #136A41 | #A7A493 | #A8650F | #B23A33 |

**Um** acento: o verde = saúde fiscal (a cor literalmente significa "seu fiscal está bem"). Grafite
para linhas técnicas; ocre/vermelho só em status. Cantos quase retos (2px), fios de 1px, elevação
mínima — precisão, não fofura.

### Tipografia — três vozes
- **Fraunces** (serifa editorial) — títulos e números-herói. Dá personalidade e ar de "documento bem
  feito"; itálico no acento. (É o que mais afasta do look de SaaS-IA, 100% sans.)
- **Hanken Grotesk** — corpo, UI, rótulos. Legível e calmo.
- **Spline Sans Mono** — dados, números, códigos, rótulos "Fig.". O mono proposital é o que faz
  "sentir ferramenta" — precisão, sem virar terminal hacker.

### Linguagem técnica (a personalidade "instrumento")
Crop marks (marcas de registro) nos painéis · rótulos **"Fig. 0X"** numerando seções como documento ·
**régua de medição** com ticks · **esquema/blueprint** que se desenha (começando pela nota) ·
**carimbo** que bate em estados resolvidos. É a camada que diz "engenharia de precisão" sem néon.

### Voz
Plano, caloroso, segunda pessoa. *"Você sabe o que está acontecendo no seu fiscal — sem precisar ser
contador."* Tranquiliza → informa → oferece o próximo passo.

## 6. Movimento

Experiência premium na mesma stack das referências: **Lenis** (scroll suave) + **GSAP/Framer Motion**
+ curvas custom. Receitas: reveal de box por *clip-wipe* + filhos escalonados; **un-blur +
scale-into-focus** em mídia; **line-mask** no headline; **draw-on** de fios/blueprint; count-up; o
**carimbo**. Easing-casa: `cubic-bezier(.16,1,.3,1)` (assentar, sem bounce). Orçamento: **1 entrada +
1 signature por tela**. Só `transform/opacity/clip-path/filter`; sempre com fallback de movimento
reduzido. *(Detalhe completo em `arkan-motion-extraction.md`.)*

## 7. Como vira produto

**Re-vestir, não re-arquitetar.** A base (Next 15 + React 19 + Tailwind v4 + shadcn) é boa e fica.
Como o tema é dirigido por tokens (`globals.css` `@theme`), **trocar tokens + revestir primitivas
propaga por todo o app**. Nenhuma função se perde; muda a pele. O Figma alinha a direção; a frota de
agentes implementa no código (`design-system` e `motion-polish` com esta identidade como referência).

## 8. O que já existe (entregáveis)

- **Identidade no Figma** (editável) — marca, lockups, estilos de cor, tipografia.
- **Protótipos de alta fidelidade** (tela Analisar Nota / Arkan) com o motion rodando.
- **Contratos de execução:** `arkan-visual-style-merge.md`, `arkan-motion-extraction.md`.
- **Plano de re-engenharia** + **frota de agentes** (`.claude/agents/`) + **CLAUDE.md** atualizado +
  `docs/HANDOFF.md`.

## 9. Recomendação / próximos passos

1. **Aprovar esta direção** (ou calibrar: verde, intensidade do motion, densidade).
2. **Fechar a identidade no Figma** e, se quiser, gerar 1–2 telas-modelo (Notas, Dashboard) lá.
3. **Aplicar no código** via a frota, com a tela **Notas como gabarito de ouro** que as demais imitam,
   e o `reviewer` segurando os gates em cada PR.
4. **Auditoria de usabilidade** sobre as telas reais (próximo entregável) — com propostas e
   antes/depois.

> Princípio que rege tudo: na dúvida entre "passável" e "memorável", a régua é *ferramenta de precisão
> na mão de um artesão.*
