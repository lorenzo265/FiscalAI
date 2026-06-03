# Arkan — Estilo Visual: Extração & Merge (fluid.glass + floema.com)

Complementa o doc de motion (`arkan-motion-extraction.md`). Aqui o foco é **aparência, personalidade
e estilo visual**: como cada site *parece e se sente*, o que importa, e como fundimos os melhores
pontos no estilo final do Arkan — **profissional, com personalidade e tecnológico**, sem cair no
visual genérico de IA.

> Honestidade: estilo visual ao vivo (WebGL/vídeo) não vem 100% no HTML. As leituras abaixo se baseiam
> em evidência concreta (estrutura, assets, metadados, tipo de mídia) + a prática conhecida dos
> estúdios (Exo Ape / Büro). Extraímos *princípios e direção*, nunca copiamos pixels ou assets.

---

## Site A — fluid.glass (estúdio Exo Ape)

**Como é, em uma frase:** clareza cinematográfica premium — "vidro": leve, nítido, sofisticado, com
muito ar e mídia grande que fala por si.

**O que define a aparência:**
- **Clareza e luz.** Fundo claro, neutros refinados; a cor vem da fotografia/vídeo full-bleed.
- **Ar generoso.** Margens largas, respiro entre seções; menos é mais.
- **Tipo confiante e econômico.** Frases curtas e seguras ("for those who build with vision"); título
  grande, corpo discreto.
- **Cinema.** Vídeo em tela cheia, transições suaves; sensação de produto caro e calmo.
- **Prova de confiança elegante.** Depoimentos 01/05 com retrato grande + nota 5.0, sem ruído.
- **Estrutura editorial-técnica.** Numeração de seções, rótulos curtos, precisão arquitetônica.

**O mais relevante p/ nós:** a **clareza** (tudo legível, calmo) e o **ar premium**. É o antídoto
contra "poluído". Personalidade: *quiet luxury* — sério, confiável, sem gritar.

---

## Site B — floema.com (estúdio Büro / Burocratik)

**Como é, em uma frase:** editorial quente e artesanal — "feito pra durar": papel, natureza,
estrutura numerada e **desenhos técnicos em linha** que dão um charme de engenharia.

**O que define a aparência:**
- **Calor de papel.** Paleta terrosa/quente, sensação tátil e natural (não o branco frio de SaaS).
- **Confiança editorial.** Headlines grandes com caráter, seções numeradas **01–05**, ritmo de revista.
- **Ilustrações wireframe / desenho técnico** (linha) — assinatura. Lê como **blueprint/esquemático**:
  é exatamente a ponte para "tecnológico" sem ser frio.
- **Hierarquia clara.** Um headline forte → pouco apoio → detalhe sob demanda.
- **Materialidade.** Texturas sutis, fios finos, composição que parece "construída", não montada.

**O mais relevante p/ nós:** o **calor + personalidade artesanal** e o **desenho técnico em linha**
(blueprint). Personalidade: *crafted & grounded* — humano, sólido, confiável.

---

## O Merge — o estilo final do Arkan

**Tese (uma linha):** *um instrumento fiscal desenhado como um blueprint de engenharia, sobre papel
quente, com a clareza cinematográfica do vidro.*

Isso resolve o pedido: **personalidade** (papel quente + editorial da Floema), **profissional**
(clareza, ar e precisão da Fluid Glass), **tecnológico** (a camada blueprint/esquemática + dados em
mono + grid técnico + motion suave). Nada de dark-neon.

### Decisões concretas (o que tomamos de cada)

| Dimensão | Decisão Arkan | Vem de |
|---|---|---|
| **Base / materialidade** | Papel quente off-white com textura sutil de pauta | Floema |
| **Ar / clareza** | Margens largas, respiro, conteúdo enxuto | Fluid Glass |
| **Tipo display** | Serifa editorial confiante (Fraunces), grande | Floema + Fluid (confiança) |
| **Tipo dados/UI** | Grotesca legível + **mono** p/ números, códigos, rótulos técnicos | nosso "instrumento" |
| **Camada tecnológica** | **Desenho técnico/blueprint**: esquemático da nota que se desenha, marcas de registro (crop marks), rótulos "FIG. 0X", ticks de medição, índice gigante editorial | Floema (wireframe) → levado a blueprint |
| **Clareza/vidro** | Um toque de **vidro fosco** (masthead translúcido, chips) — clareza como cue tech, com parcimônia | Fluid Glass |
| **Cor** | Tinta + papel + **um verde** (marca/saúde fiscal). Linhas técnicas em grafite; verde marca os pontos-chave | nosso sistema |
| **Estrutura** | Grid visível, fios 1px, numeração 01–06, cantos quase retos — não cards flutuando | Floema + instrumento |
| **Prova/parecer** | Veredito calmo + carimbo (assinatura própria) | Fluid (prova) + nosso |
| **Motion** | Lenis + GSAP (reveals de box, line-mask, draw-on do blueprint) | ambos (ver doc de motion) |

### O que NÃO trazemos (quarentena de IP)
Fotos, vídeos, ilustrações específicas, fontes proprietárias, layouts literais. Só direção e princípios.

### A personalidade resultante
Sério mas humano. Preciso mas calmo. Técnico mas legível. Um cartório do futuro: o documento oficial
que você *gosta* de olhar porque é lindamente desenhado e fácil de entender.

---

## Escopo: PoC agora × plano completo depois

**Nesta PoC (implementada na tela Analisar Nota):**
- Camada blueprint: esquemático da nota que se desenha, crop marks, rótulos FIG., ticks de medição.
- Índice editorial gigante (02) como elemento de personalidade.
- Masthead com vidro fosco; refino de tipo/espaço; mais hierarquia.
- Mantém todo o motion e as funções.

**Depois (aumentar complexidade — rodando múltiplos agentes no Claude Code):**
- Sistema completo de blueprint (ícones/ilustrações esquemáticas próprias para cada feature).
- Transições entre telas, pinned/parallax sutil, página-storytelling no onboarding.
- Design system tokenizado (Tailwind + CSS vars) + biblioteca de componentes (shadcn restyled).
- Propagar a linguagem para Início, Histórico, Perfil, Regras — consistência total.
- Dark mode re-derivado, modo "vidro" para overlays, microilustrações animadas em empty states.

> A divisão certa para a frota: um agente cuida do **design system/tokens**, outro de **componentes**,
> outro de **motion**, com este documento + o de motion como contrato comum.
