# Auditoria de UX — Frontend Arkan
## 2026-06-10 | Modo: [AUDIT] usabilidade | Meta: uso sem tutorial, controle total da empresa em segundos

Base factual: varredura do código (`analista-fiscal-web`, ~45 rotas), `docs/HANDOFF.md` (re-engenharia Fases 0–4 concluída) e a pesquisa de obrigações 2026 (`validacao-cobertura-mei-simples-2026.md`).

**Princípio-guia:** o dono de PME abre o app com UMA pergunta na cabeça — *"estou bem com o governo e quanto vou pagar?"* Toda mudança abaixo serve a essa pergunta. Regra dos 5 segundos: se uma tela não responde o que importa em 5s, ela está errada.

---

## O que já está certo (não mexer)

A re-engenharia entregou fundamentos raros: tradução CFOP/CST/NCM (PT claro + código em `<abbr>` mono), status sempre cor+ícone+palavra, empty states com próxima ação, wizards RHF+Zod com validação por passo, navegação de 11 itens sem jargão, health score na home, charts lazy, AA nos dois temas, reduced-motion. **O esqueleto é bom. Os problemas restantes são de linguagem, hierarquia e fluxo.**

---

## As 12 mudanças, por impacto

### Bloco 1 — Linguagem (o maior gap restante)

A tradução §7 cobriu CFOP/CST/NCM, mas **parou nos códigos de nota**. As siglas que o dono encontra TODO MÊS continuam cruas:

**1. Traduzir as obrigações na agenda e em todo o app.** "DAS", "DCTF", "eSocial", "PGDAS-D", "DEFIS" aparecem secos na agenda e nos cards. Aplicar o mesmo padrão do gabarito Notas — frase principal em PT + sigla em `<abbr>` mono secundário:
   - DAS → **"Guia mensal de impostos"** · DAS
   - PGDAS-D → **"Declaração do faturamento do mês"** · PGDAS-D
   - DEFIS → **"Declaração anual da empresa"** · DEFIS
   - eSocial → **"Informações dos funcionários ao governo"** · eSocial
   - DCTFWeb → **"Declaração dos impostos da folha"** · DCTFWeb
   Criar `lib/traducao/obrigacoes.ts` central (hoje cada tela resolve sozinha) e consumir em agenda, home, fiscal e notificações.

**2. "Fator R" e "Anexo" nunca como termo principal.** O simulador e a tela fiscal expõem "Fator R" e "Anexo III/V" sem explicação. Trocar para o efeito, não o mecanismo:
   - Fator R → **"Seu desconto por ter folha de pagamento"** com medidor: *"Sua folha é 31% do faturamento — acima de 28%, você paga a alíquota menor ✓"*
   - Anexo III/V → **"Categoria de imposto da sua atividade"**
   O termo técnico fica disponível num "ver detalhe técnico" (para conversar com o contador), nunca como rótulo.

**3. Tributos do health score com uma linha de contexto.** ICMS/ISS/INSS/FGTS aparecem como siglas nuas nas miniaturas. Cada um ganha aposto fixo: "ICMS — imposto estadual sobre vendas", "FGTS — fundo do funcionário". Custo: um mapa de 8 strings.

### Bloco 2 — Hierarquia: a resposta de 5 segundos

**4. Home = 3 respostas, nesta ordem, nada antes delas:**
   1. **"Estou bem?"** — health score com Carimbo (já existe, manter no topo)
   2. **"O que tenho que fazer / pagar agora?"** — o próximo vencimento com valor em destaque serif e botão único "Pagar guia" (PIX já existe)
   3. **"Quanto vou pagar este mês?"** — imposto estimado do mês corrente
   Tudo mais (gráficos, histórico, alertas secundários) desce abaixo da dobra. Hoje a home tem widgets demais competindo; auditar `components/home/*` e rebaixar o que não responde às 3 perguntas.

**5. Urgência em 3 níveis na agenda e na home.** Hoje vencimento em 2 dias e em 20 dias têm o mesmo peso visual. Com a multa do PGDAS-D automática desde 2026 (LC 214/2025, sem notificação prévia), atraso = dinheiro perdido no dia seguinte. Três estados com cor+ícone+palavra (padrão já existente no `Pill`):
   - 🔴 danger **"Vence em 2 dias"** (≤3 dias) — também vira card fixo no topo da home
   - 🟠 ochre **"Vence esta semana"** (≤7 dias)
   - neutro **"Vence em 20 dias"**

**6. Monitores de limite como widgets de régua (novo, dados já existem).** A pesquisa fiscal mostrou que estourar limite sem perceber é o erro nº 1 da PME. O app tem faturamento + notas + open finance — basta exibir: régua de progresso anual contra R$81k (MEI) / R$3,6M (sublimite) / R$4,8M (teto), com projeção: *"No seu ritmo, você atinge o limite em outubro"*. Componente `Ruler` do blueprint já existe e é literalmente uma régua — é o widget-assinatura perfeito.

### Bloco 3 — Fluxo: menos passos até a ação

**7. Uma ação primária por tela, verbo do dono.** Auditar cada rota: a home tem "Pagar guia"? Notas tem "Emitir nota"? Funcionários tem "Pagar folha"? Onde a ação primária hoje é técnica ("Transmitir", "Gerar PGDAS"), trocar pelo resultado: "Enviar declaração ao governo". Botão primário verde, único, sempre no mesmo lugar.

**8. Onboarding: valor antes de formulário.** Hoje o wizard de 5 passos pede dados antes de mostrar qualquer benefício, e perde progresso ao fechar a aba. Mudar para: (a) pedir só CNPJ no passo 1 e **pré-preencher tudo via BrasilAPI** (integração já existe no backend — razão social, CNAE, regime); (b) mostrar o dashboard imediatamente com o que já dá para inferir, e pedir o resto (certificado, banco) *em contexto*, quando a feature precisar ("Para emitir notas, conecte seu certificado — 2 min"); (c) persistir progresso (localStorage/Dexie já no stack).

**9. Erros que dizem o que fazer.** `ErrorState` genérico ("Algo deu errado") vira sempre: o que houve em PT simples + o que fazer + botão da ação. Ex.: *"Não conseguimos falar com a Receita agora. Seus dados estão salvos — tente de novo em alguns minutos."* + "Tentar de novo". Nunca expor mensagem técnica/stack; mapear os ~60 `DomainError` do backend para frases humanas em `lib/traducao/erros.ts`.

**10. Tabelas viram cards no mobile.** A lista de notas tem 7 colunas com scroll horizontal no celular — o dono de PME vive no celular. Padrão: ≤768px renderiza card por nota (cliente em serif, valor em mono destaque, status Pill, data) com as demais infos no detalhe. Replicar em lançamentos, contas a pagar/receber e funcionários.

### Bloco 4 — Confiança

**11. Assistente real e onipresente.** O chat flutuante ainda é mock ("respostas simuladas") — prometer IA e entregar simulação corrói a confiança que a identidade inteira foi construída para gerar. Prioridade: ligar ao backend (`assistente` com citação obrigatória já pronto) ou esconder o botão até estar real. Quando real: acessível de toda tela e com **perguntas prontas contextuais** ("Por que meu imposto subiu?" na tela fiscal) — o dono não sabe o que perguntar.

**12. Confirmação com prova.** Após qualquer ato fiscal (pagar, transmitir, emitir), tela de confirmação com Carimbo + frase de efeito (*"Declaração enviada. Você está em dia."*) + recibo/protocolo baixável. O momento pós-ação é onde a confiança se forma; o `Carimbo` existe exatamente para isso — usá-lo como rito consistente em todos os fluxos, não só em notas.

---

## Sequência recomendada (4 PRs)

| PR | Conteúdo | Por quê primeiro |
|---|---|---|
| 1 | Bloco 1 inteiro (`lib/traducao/obrigacoes.ts` + erros + apostos de tributos) | Maior ganho por hora; zero risco de regressão; remove a necessidade nº 1 de "tutorial" |
| 2 | Hierarquia da home (3 respostas) + urgência em 3 níveis | É a tela de todo dia; multa automática 2026 dá urgência real |
| 3 | Cards mobile + ação primária por tela | Dono de PME é mobile-first |
| 4 | Onboarding por CNPJ + monitores de limite + assistente real | Exigem backend; maior esforço |

**Gate de aceite por tela (anexar ao checklist do reviewer):** (a) responde sua pergunta-chave em 5s; (b) zero sigla sem tradução visível; (c) uma ação primária clara; (d) urgência diferenciada quando há prazo; (e) usável com polegar a 375px.
