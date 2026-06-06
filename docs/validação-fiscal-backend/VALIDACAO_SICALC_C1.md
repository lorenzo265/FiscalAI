---
titulo: Checklist de validação Sicalc — C1 (SELIC mesmo mês)
status: aguardando validação do usuário
origem: AUDITORIA_FISCAL_BACKEND.md · issue C1 (CRÍTICO) · esteira FA1
data: 2026-06-05
bloqueia: commit do FA1 (calcula_selic.py + test_selic_mora.py — hoje segurados fora dos commits)
---

# Validação Sicalc — C1: juros no mesmo mês do vencimento

> **Por que validar:** o FA1 mudou regra que afeta **valor cobrado do cliente** (multa + juros de
> mora). Antes de commitar, confirme contra a ferramenta oficial. O FA1 está **segurado** no working
> tree (não commitado) até este checklist fechar.

## Onde rodar (ferramenta oficial)

- **Sicalc Web** (Receita Federal) — "Cálculo e emissão de DARF com acréscimos legais":
  acesse pelo site da RFB → busque **"Sicalc"** / **"Cálculo de DARF em atraso"**
  (gov.br/receitafederal → Serviços → *Sicalc Web*), ou pelo **e-CAC** (Centro Virtual de
  Atendimento) → *Pagamentos e Parcelamentos*.
- Informe um **código de receita** qualquer de teste (ex.: DAS/DARF), **valor principal R$ 1.000,00**,
  a **data de vencimento** e a **data de pagamento** dos casos abaixo. O Sicalc devolve **multa de
  mora** e **juros de mora** separados — é exatamente o que comparamos.

## A regra sob teste (o que o FA1 corrigiu)

Lei 9.430/1996 art. 61 §3º + metodologia Sicalc: **juros de mora (SELIC acumulada + 1% do mês de
pagamento) só incidem a partir do 1º dia do mês SUBSEQUENTE ao vencimento.** Pagamento **dentro do
mês do vencimento** → **só multa de mora (0,33%/dia, teto 20%); juros = R$ 0,00.**
O bug anterior somava 1% (R$ 10,00 em R$ 1.000) mesmo no mesmo mês — e o golden test travava o valor
errado.

## Casos a conferir (principal = R$ 1.000,00)

| # | Vencimento | Pagamento | Dias | Multa esperada | Juros esperados | Total acréscimos |
|---|---|---|---|---|---|---|
| 1 | 20/05/2025 | 25/05/2025 | 5 | R$ 16,50 (0,33%×5) | **R$ 0,00** | R$ 16,50 |
| 2 | 20/05/2025 | 10/06/2025 | — | multa (dias/teto) | **1% (R$ 10,00) + SELIC de maio** | multa + juros |
| 3 | 20/05/2025 | 31/05/2025 | 11 | R$ 36,30 (0,33%×11) | **R$ 0,00** (ainda é maio) | R$ 36,30 |

**O ponto crítico:** casos **1 e 3 (mesmo mês) devem ter juros = R$ 0,00**. Se o Sicalc cobrar juros
neles, me avise. O caso 2 confirma que no mês subsequente o 1% volta a incidir.

> Obs. caso 2: o valor exato da SELIC acumulada depende da tabela SELIC seedada no banco; o que
> importa validar aqui é a **presença do 1% (R$ 10,00)** no mês subsequente, ausente nos casos 1 e 3.

## Onde isso vive no código (para conferência cruzada)

- Algoritmo: `app/modules/multa_juros/calcula_selic.py` — guard
  `date(pagamento.ano, pagamento.mes, 1) > date(venc.ano, venc.mes, 1)` controla o `acrescimo_mes` (1%).
- Goldens: `tests/unit/multa_juros/test_selic_mora.py` —
  `test_multa_5_dias_dentro_mesmo_mes` (caso 1, juros 0) e
  `test_acrescimo_mes_incide_em_mes_subsequente` (caso 2, 1% incide).

## Como reportar o resultado

- ✅ **Bateu** (casos 1 e 3 sem juros; caso 2 com 1%): me avise — eu **commito o FA1**
  (`calcula_selic.py` + `test_selic_mora.py`) e fecho a esteira fiscal.
- ❌ **Divergiu**: me mande o print/valores que o Sicalc retornou (multa e juros de cada caso) —
  eu reajusto algoritmo + golden antes de commitar.
