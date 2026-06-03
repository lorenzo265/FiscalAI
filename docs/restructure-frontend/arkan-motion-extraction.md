# Arkan — Design System Extraído (fluid.glass + floema.com)

Foco: **animações** e **boxes de informação**. Este documento destila o sistema de motion das duas
referências e o traduz em receitas concretas e reutilizáveis para o **Arkan** (app da Arkan Fiscal
Technologies). Princípio das leis de extração: extraímos *o sistema*, nunca copiamos pixels ou assets.

> Honestidade técnica: o motion ao vivo dessas SPAs não vem no HTML extraído. As receitas abaixo são
> fundamentadas em (a) evidência estrutural das páginas, (b) a stack confirmada dos estúdios — Lenis +
> GSAP ScrollTrigger + CustomEase —, e (c) padrões premium documentados desses estúdios (Exo Ape /
> Büro). Tudo abaixo é implementável com transform/opacity/clip-path/filter, com fallback acessível.

---

## 1. Teardown — o que cada site faz

### fluid.glass (estúdio Exo Ape) — cinematográfico, premium, "clareza"
- **Scroll suave (Lenis)** com física/inércia — a sensação número 1 de "premium". Nada de scroll seco.
- **Mídia full-bleed** (vídeos Vimeo 2160p) que entram com **un-blur + scale-into-focus** (a imagem
  começa levemente desfocada e escalada ~1.08 e assenta nítida em 1.0).
- **Reveals na entrada do viewport** (ScrollTrigger), não tudo de uma vez.
- **Carrossel de depoimentos 01/05** com retrato grande + citação — prova de confiança.
- Tipo de cópia: frases curtas e seguras ("for those who build with vision"), muito ar.
- Easing: curvas custom (CustomEase) — assentar suave, sem bounce.

### floema.com (estúdio Büro / Burocratik) — editorial, natural, "made to last"
- **Seções numeradas 01–05**, cada uma com imagem grande e título confiante.
- **Ilustrações wireframe que se desenham** (draw-on SVG) — assinatura.
- **Reveals escalonados** sequenciais (índice a índice, da esquerda/de cima).
- Composição editorial: um headline grande → pouco apoio → detalhe sob demanda.
- Scroll narrativo e calmo; o movimento serve à leitura, não compete com ela.

### O que TOMAMOS (foco do pedido)
1. **Lenis smooth scroll** como base sensorial premium.
2. **Reveal de box por clip-path wipe** + conteúdo escalonado dentro.
3. **Un-blur + scale-into-focus** para mídia/preview (assinatura Exo Ape).
4. **Line-mask reveal** do headline (linha sobe de dentro de máscara overflow:hidden).
5. **Draw-on** de fios/margens (assinatura Büro) → nossa margem-razão verde.
6. **Stagger sequencial** com CustomEase.
7. **Count-up** de métricas na revelação.

### O que DEIXAMOS (quarentena de IP)
Vídeos, fotos, ilustrações wireframe, fontes proprietárias, layouts literais. Nada disso é reusado.

---

## 2. Tokens de motion do Arkan (o contrato)

```
/* Easing — assentar premium, sem bounce */
--ease-settle:  cubic-bezier(0.16, 1, 0.3, 1);    /* expo-out: entradas e estados */
--ease-reveal:  cubic-bezier(0.62, 0.05, 0.01, 0.99); /* reveals fortes (wipe/mask) */
--ease-stamp:   cubic-bezier(0.34, 1.56, 0.40, 1);    /* SÓ o carimbo: leve overshoot */

/* Durações */
--dur-micro:    160ms;   /* hover, foco, toggle */
--dur-base:     320ms;   /* mudanças de estado */
--dur-reveal:   780ms;   /* reveals de box / mídia */
--dur-line:     640ms;   /* draw-on de fios/margem */
--stagger:      70ms;    /* entre irmãos */

/* Scroll (Lenis) */
lerp: 0.09;  wheelMultiplier: 1.0;  /* suave, sem exagero de inércia */
```

Regra de ouro herdada da skill: **detalhe no craft, calma no conteúdo.** Mais animação no *como*,
conteúdo enxuto no *quê*. Tudo respeita `prefers-reduced-motion` e nunca bloqueia a leitura/ação.

---

## 3. Receitas — os "boxes de informação" (o coração do pedido)

### Receita A — Box revela por wipe + conteúdo escalonado
O bloco entra com um corte (clip-path) e o conteúdo interno sobe em sequência.
```
Gatilho:   box entra no viewport (ScrollTrigger start "top 85%")
Box:       clip-path inset(0 0 100% 0) → inset(0 0 0% 0)   | --dur-reveal | --ease-reveal
           (acompanha translateY 16px → 0, opacity 0 → 1)
Filhos:    cada filho y 18px + opacity 0 → 0, stagger --stagger, --ease-settle
Fallback (reduced-motion): aparece sem movimento (opacity 1, sem clip)
```

### Receita B — Mídia un-blur + scale-into-focus (preview da nota, imagens)
```
Mídia:     scale(1.08) + filter blur(10px) + opacity .0  →  scale(1) blur(0) opacity 1
Duração:   --dur-reveal (mídia) | --ease-reveal
Uso:       preview da nota fiscal, thumbnails, qualquer imagem que entra
```

### Receita C — Headline line-mask (assinatura premium)
```
Markup:    cada linha em .line{overflow:hidden}; dentro .line>span (o texto)
Anim:      span translateY(110%) → 0, por linha, stagger --stagger, --ease-reveal
Quando:    no load da tela e/ou ao entrar no viewport
```

### Receita D — Draw-on de fio/margem (Büro → nossa margem-razão)
```
Fio:       altura/largura 0 → 100% | --dur-line | --ease-settle
Uso:       a margem verde do livro-razão de verificação desce conforme os agentes concluem;
           sublinhados de links desenham no hover
```

### Receita E — Count-up de métrica
```
0 → valor (ex.: Conformidade 0% → 92%) em ~1s, easing cubic ease-out, fonte mono tabular
Dispara junto com o reveal do box de parecer
```

### Receita F — Carimbo (assinatura própria do Arkan)
```
Stamp:     opacity 0 + scale 1.7 + rotate -22deg → opacity .92 + scale 1 + rotate -7deg
Duração:   500ms | --ease-stamp (único lugar com overshoot)
Extra:     anel de "tinta" que expande e some atrás do carimbo
Quando:    parecer final aparece (nota conferida)
```

### Micro-interações premium (sutis, ajudam a usar)
- Botão primário: leve "magnetismo" + seta que desliza no hover.
- Dropzone: cantos de mira (corner ticks) aparecem + borda fica verde no hover/dragover.
- Links de ação: sublinhado verde que desenha; gap que abre no hover.
- Hover de mídia: scale 1.0 → 1.03 lento.

---

## 4. Stack de implementação (para os agentes de build)

```
Scroll:    Lenis (lerp .09) sincronizado ao GSAP ticker
Motion:    GSAP + ScrollTrigger (reveals na entrada) + CustomEase (curvas acima)
Fallback:  conteúdo visível por padrão; JS só ENRIQUECE (progressive enhancement).
           Se GSAP/Lenis não carregar, a tela funciona com scroll nativo e sem reveals.
Perf:      animar só transform/opacity/clip-path/filter; honrar prefers-reduced-motion;
           60fps em Android médio — se não segurar, simplificar.
React:     Framer Motion (variants + whileInView + staggerChildren) reproduz A–E;
           Lenis como provider de scroll suave no shell.
```

---

## 5. Como isso vira "premium e fácil de usar"
A experiência premium vem de **3 coisas baratas e seguras**: (1) scroll suave (Lenis), (2) reveals de
box com wipe + un-blur na entrada, (3) line-mask no headline. Tudo o resto é micro. O "fácil de usar"
é garantido porque o movimento nunca esconde conteúdo, nunca atrasa a ação, e sempre tem fallback —
o craft está na forma, a calma está no conteúdo.
