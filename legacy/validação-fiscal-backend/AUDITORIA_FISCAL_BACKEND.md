# Auditoria Fiscal — Backend (código real)

> **Modo:** `[VERIFY]` — Compliance Review Gate aplicado sobre o código implementado, não sobre o plano.
> **Data:** 2026-06-04
> **Escopo auditado:** 14 algoritmos `app/modules/**/calcula_*.py` + 4 seeds de tabela tributária (`alembic/versions/`).
> **Não auditado nesta passada:** clients de integração (SERPRO/Focus/Pluggy), services de orquestração, SPED, camada UX.

---

## Resumo executivo

**14 issues** — **1 CRÍTICO, 5 MAJOR, 8 MINOR.** O núcleo está sólido; os erros estão em arestas e em defasagem temporal, não na espinha dorsal.

| Gate | Status | Observação |
|------|--------|-----------|
| 1 — Fiscal Accuracy | ❌ FAIL | C1 (SELIC), M2 (tabelas 2026), M3 (CSLL retida) |
| 2 — Data Integrity | ✅ PASS | Decimal/NUMERIC, chaves como string, CNPJ válido |
| 3 — Code Quality | ✅ PASS | Funções puras, golden-tested, zero `Any` nos contratos |
| 4 — UX Compliance | n/a | Backend — não auditado nesta passada |
| 5 — Integration Safety | n/a | Clients externos não lidos nesta passada |

**Ordem de remediação recomendada:** (1) corrigir SELIC + reescrever golden → (2) seedar vigências 2026 de INSS/IRRF → (3) simetrizar compensação de CSLL.

---

## 🔴 CRÍTICO (bloqueia produção)

### C1 — SELIC: 1% de juros indevido em pagamento no mesmo mês do vencimento

- **Arquivo:** `app/modules/multa_juros/calcula_selic.py:117-119`
- **Gate 1 (Fiscal Accuracy): ❌ FAIL**

```python
# Aplica-se sempre que há atraso (mesmo se pagamento no mesmo mês do vencimento)
acrescimo_mes = (valor * Decimal("0.01")).quantize(...)
```

O acréscimo de 1% é somado **sempre que `dias_atraso > 0`**, inclusive quando o pagamento ocorre no mesmo mês do vencimento. Pela metodologia Sicalc (Lei 9.430/1996 art. 61 §3º), **os juros de mora só incidem a partir do 1º dia do mês subsequente ao vencimento**. Pagamento dentro do mês do vencimento tem **apenas multa de mora (0,33%/dia), juros = 0**.

- **Exemplo:** DAS vence 20/05, paga 25/05. O sistema cobra multa R$16,50 **+ R$10,00 de "juros"** sobre R$1.000. Correto seria só a multa — **R$10,00 cobrados a mais**.
- **Agravante:** o golden test `tests/unit/multa_juros/test_selic_mora.py:81` (`test_multa_5_dias_dentro_mesmo_mes`, linha 91) **assere o valor errado como gabarito** → a barreira anti-regressão está protegendo o bug.
- **Propaga** para denúncia espontânea (mesmo `acrescimo_mes`).

**Correção:** condicionar o 1% a `date(pagamento.year, pagamento.month, 1) > date(venc.year, venc.month, 1)`. Reescrever `test_multa_5_dias_dentro_mesmo_mes` para `acrescimo_mes_pagamento == 0`. **Validar contra simulação real no Sicalc antes de mergear.**

---

## 🟠 MAJOR

### M2 — Tabelas tributárias 2026 ausentes (INSS + IRRF)

- **Arquivos:** `alembic/versions/0016_sprint10_pessoal_tabelas.py:367`, `alembic/versions/0045_sprint19_6_pr1_seed_inss_2024.py`
- **Gate 1: ❌ FAIL para competências ≥ 2026**

Última vigência seedada de INSS = `valid_from=2025-01-01, valid_to=NULL`; IRRF = fev/2024. **Hoje é jun/2026** — toda folha de competência 2026 usa a faixa 1 do INSS de 2025 (mínimo R$1.518), defasada do mínimo de 2026, e o IRRF de 2024 sem a ampliação de isenção de 2026. Os valores 2024/2025 estão **corretos** (conferidos faixa a faixa); falta a vigência 2026.

> É a pendência consciente #7 do `log_agente.md`, mas deixou de ser teórica: calcula folha errada em produção agora.

**Correção:** inserir vigências 2026 via SCD. Confirmar normas: Portaria do mínimo 2026 + eventual reforma do IR PF (Lei 15.270/2025), se aplicável à competência.

### M3 — CSLL trimestral não deduz retenção na fonte (CSRF)

- **Arquivo:** `app/modules/lucro_presumido/calcula_csll.py:63`
- **Gate 1: ⚠️ WARN → FAIL**

O IRPJ tem `irrf_a_compensar` (`calcula_irpj.py:84`), mas a CSLL **não tem** `csll_a_compensar`. Empresa LP de serviços que sofre retenção PCC (4,65% = 1% CSLL + 3% Cofins + 0,65% PIS) na fonte PJ→PJ **não consegue abater a CSLL retida** → recolhe em duplicidade. Assimetria injustificada com o IRPJ.

**Correção:** adicionar parâmetro `csll_a_compensar` simétrico ao do IRPJ (`min(csll_a_compensar, csll_devida)`, saldo credor para o trimestre seguinte).

### M4 — IRRF não deduz pensão alimentícia judicial

- **Arquivo:** `app/modules/pessoal/calcula_irrf.py:14` (docstring: *"pensao_alimenticia (não tratada neste PR)"*)

Pensão alimentícia por decisão judicial é **dedução legal da base do IRRF** (Lei 9.250/95 art. 4º II / art. 8º II "f"). Sem ela, o IRRF do alimentante é superestimado. Propaga para férias, 13º e rescisão (todos chamam `calcular_irrf_mensal`).

**Correção:** adicionar parâmetro `pensao_alimenticia` à base.

### M5 — IRRF sem opção de desconto simplificado mensal

- **Arquivo:** `app/modules/pessoal/calcula_irrf.py:65`

A legislação (Lei 14.848/2024) permite o **desconto simplificado mensal** (25% do teto da 1ª faixa) como alternativa às deduções legais; o sistema deve aplicar **o que for mais benéfico** ao contribuinte. O cálculo usa só a tabela progressiva com deduções legais → IRRF superestimado para quem se beneficiaria do simplificado.

**Correção:** implementar `min(IRRF_legal, IRRF_simplificado)`.

---

## Parte 2 — Issues recuperadas (auditoria de completude · 2026-06-04)

> O resumo executivo anunciava 14 issues, mas o corpo acima documentava só 5 (C1, M2–M5).
> Duas auditorias de completude de contexto fresco (tributos-core + folha/relatórios) sobre os 30
> `calcula_*.py` + seeds recuperaram **12 issues novas** (4 MAJOR, 8 MINOR). Numeração unificada
> abaixo (M6–M9 majors, m1–m8 minors). Total consolidado: **C1 + M2–M9 + m1–m8 = 17 issues.**

### 🟠 MAJOR (recuperados)

#### M6 — Presunção LP de serviços de saúde/profissionais não-hospitalares cai no default 8% (deveria 32%)
- **Arquivo:** `alembic/versions/0019_sprint11_presuncao_lp.py:96-209` (seed) + `lucro_presumido/repo.py:78-82` (fallback).
- **Gate 1: ❌ FAIL.** O seed mapeia 32% só para CNAEs `69/71/73/70/74/82`. O próprio docstring declara que `75` (veterinária), `855` (cursos), `862/863/869` (consultórios médicos/odontológicos não-hospitalares) e `96` (serviços pessoais) **também são 32%** (Lei 9.249/95 art.15 §1º III) — mas essas linhas **não foram inseridas**. `resolver_por_cnae` cai no default `comercio_industria` 8% → clínica/dentista/veterinário presumido a 8% em vez de 32%. **Subtributação de 4× na base** — exatamente o público-alvo (consultórios).
- **Exemplo:** consultório (CNAE 8630), receita tri R$300k: sistema IRPJ R$3.600; correto R$18.000 → **R$14.400/tri a menos** (idem CSLL).
- **Correção:** inserir no seed (mesma vigência SCD) as linhas 32% para patterns `75/855/862/863/869/96` + golden provando que `8630` resolve 32%.

#### M7 — SCD CBS/IBS: 3 vigências abertas (`valid_to=NULL`) com chaves distintas → overlap; trigger nunca fecha
- **Arquivo:** `alembic/versions/0034_sprint14_reforma_aliquotas.py:103-115` (trigger) + `141-207` (seed).
- **Gate 1: ⚠️→FAIL (higiene SCD §8.3).** As 3 fases (`teste_2026`/`transicao_2027_2032`/`regime_pleno_2033`) entram com `valid_to=NULL`; o trigger tem chave `(fase, regime, cnae, classif)` e, como cada linha tem `fase` distinta, **nunca fecha o `valid_to` anterior** → três intervalos `[…, ∞)` sobrepostos. Só não quebra porque `repo.py:204` filtra por `fase` derivada da data — a higiene está no código, não na tabela. Armadilha latente para qualquer outro consumidor.
- **Correção:** seedar `valid_to` explícito (`teste_2026`→2026-12-31; `transicao`→2032-12-31; `pleno`→NULL) **ou** trocar a chave do trigger para fechar corretamente.

#### M8 — Provisão de encargos sobre folha usa só 20% (omite RAT/SAT + Terceiros) → subprovisiona passivo
- **Arquivo:** `provisoes/calcula_provisao.py:36` (`_ALIQ_INSS_PATRONAL=0.20`), aplicado em `:108-110`.
- **Gate 1: ❌ FAIL (LP/Lucro Real).** Provisão de INSS sobre férias/13º usa só a cota patronal 20% (Lei 8.212/91 art.22 I), omitindo **RAT/SAT 1–3%** (art.22 II, ajustável por FAP) e **Terceiros/Sistema S ~5,8%**. Encargo real típico ~26,8–28,8%. Subprovisão de ~⅓ da linha; distorce passivo trabalhista (Balanço) e custo (DRE). **Nuance de regime:** SN Anexos I–III têm CPP no DAS (desonerada) — a correção deve ser **regime-aware**, não aplicar 20%+ a todos.
- **Agravante:** golden `test_calcula_provisao.py:53` assere `inss_ferias==222.22` como gabarito → barreira protege a subprovisão.
- **Correção:** parametrizar a alíquota patronal previdenciária (regime-aware; componentes 20%+RAT×FAP+Terceiros vindos de SCD por CNAE/grau de risco). **Sem fabricar RAT por CNAE** — ver decisão de execução (parametrização + seed RAT como follow-up).

#### M9 — DRE soma "Outras Receitas" (4.9.x, não-operacionais) dentro da Receita Operacional Bruta
- **Arquivo:** `relatorios/calcula_dre.py:58` (`_COD_RECEITA_RAIZ="4"`) + `:191`.
- **Gate 1: ❌ FAIL (Lei 6.404/76 art.187).** A ROB soma todo o prefixo `4.*`, incluindo `4.9 Outras Receitas` (destino de receitas não classificadas). Qualquer saldo em `4.9.x` infla ROB, Receita Líquida, **todas as margens, Giro do Ativo** e gera divergência falsa na reconciliação contábil×fiscal do `dre_aux_lp`. Golden nunca testa `4.9.x`.
- **Correção:** somar ROB apenas de `4.1` (Receita Operacional); tratar `4.9` como linha separada abaixo do resultado operacional + golden com `4.9.99`.

### 🟡 MINOR (recuperados)

| ID | Arquivo | Achado | Correção |
|---|---|---|---|
| m1 | `reinf/calcula_retencao.py:28-29,120` | IRRF 1,5% **sempre** retido; docstring "sem limite mínimo" é incorreta — IRRF (cód. 5952/1708) tem DARF mínimo R$10 (Lei 9.430/96 art.68 §1º). | Documentar/implementar piso R$10 com acumulação mensal, ou ao menos corrigir o comentário. |
| m2 | `alembic/versions/0020_..._icms_efd_reinf.py:200` | RJ com `interna=20%` **E** `fecp=2%` → soma interna+FECP daria 22% (dupla contagem). Interna do RJ é 18%. FECP hoje é campo morto (algoritmo ignora). | `interna=0.18` (mantendo `fecp=0.02`); definir no algoritmo se efetiva = interna+fecp. Revisar UFs que subiram alíquota 2024-25. |
| m3 | `lucro_presumido/calcula_pis_cofins.py:71-75` | `exclusoes > receita` aborta o mês; estouro legítimo (cancelamentos de competências anteriores, exportação) descarta dedução. | `base=max(0, receita−exclusoes)` + transportar excedente (carryover). |
| m4 | `pessoal/calcula_hora_extra.py:144-173` | Adicional noturno ignora **hora reduzida 52'30"** (CLT art.73 §1º) → subestima ~14% das horas noturnas. Rotulado "simplificação" mas é legalmente incorreto. | Fator `52,5/60` na hora noturna, ou marcar resultado como estimativa. |
| m5 | `pessoal/calcula_hora_extra.py:111-141` | Hora extra **sem reflexo em DSR** (Lei 605/49 art.7º, Súmula 172 TST). | Documentar no `ResultadoHoraExtra` que é valor parcial; DSR em sprint dedicada. |
| m6 | `pessoal/calcula_distribuicao.py:109-129` | `valor_tributavel` passa **não-quantizado** a `calcular_irrf_mensal`; se `limite_isento_apurado` vier com >2 casas (de `receita×presunção`), a base do IRRF carrega casas extras. | Quantizar `valor_tributavel` antes do IRRF. |
| m7 | `pessoal/calcula_prolabore.py:23` (docstring) | Docstring crava `(dependentes × 189,59)`; o valor real vem da SCD `FaixaIrrf.deducao_dependente`. Induz erro quando a dedução mudar. | Remover literal; referir à SCD. |
| m8 | `pessoal/calcula_13o.py:104-106` + `rescisao.py:214` | `_validar_avos` exige `[1,12]`; admissão+demissão no mesmo mês <15 dias gera `avos=0` legítimo (Dec. 57.155/65) → 13º levanta `ValueError`; rescisão aceita 0 → assimetria entre módulos. | Permitir `avos=0` no 13º (retorna zero); documentar regra dos 15 dias no service. |

> **Saúde fiscal (completude):** a espinha dorsal (DAS, IRPJ/CSLL/PIS-Cofins LP, ICMS débito×crédito,
> INSS/IRRF/FGTS/13º/férias/rescisão, parcelamento, balanço/DFC) está **correta valor a valor**. Os
> defeitos novos concentram-se em **completude de seed** (M6), **higiene SCD** (M7), **subprovisão de
> encargos** (M8) e **classificação contábil de fronteira** (M9) — mais arestas trabalhistas/contábeis
> nos minors. Nenhum furo na matemática do núcleo.

### M6 — ICMS sem DIFAL (EC 87/2015)

- **Arquivo:** `app/modules/icms/calcula_icms.py`
- **Gate 1: ⚠️ WARN**

A apuração débito×crédito está correta e o helper `aliquota_interestadual` existe, mas **não há cálculo de DIFAL** (partilha origem×destino) para venda a consumidor final não-contribuinte em outro estado — item marcado como *"implementar obrigatoriamente para e-commerce"*. PME de e-commerce fica descoberta.

**Correção:** decidir entre declarar out-of-scope explícito (→ marketplace) **ou** implementar a partilha DIFAL.

---

## 🟡 MINOR / WARN

| # | Arquivo | Achado | Correção |
|---|---------|--------|----------|
| m1 | `alembic/versions/0002_sprint2_ingestao_fiscal.py:103` | `anexo CHAR(3)` armazena `'V  '` com espaços; `resolver_anexo_fator_r` faz `anexo not in ("III","V")` e **levantaria ValueError** se o repo não der `.strip()`. | Trocar por `VARCHAR`. Confirmar comportamento no repo. |
| m2 | `app/modules/lucro_presumido/calcula_pis_cofins.py:71` | `exclusoes > receita` levanta erro — bloqueia mês legítimo com muitos cancelamentos de vendas anteriores. | Pisar em zero em vez de falhar. |
| m3 | `alembic/versions/0016_sprint10_pessoal_tabelas.py:432` | Citação errada: tabela IRRF fev/2024 veio da **MP 1.206/2024**, não "MP 1.171/2024" (essa é 2023). Valores corretos. | Corrigir a string `fonte`. |
| m4 | `app/modules/pessoal/calcula_inss.py:104` | Variável `acumulado` calculada e nunca usada (dead code). | Remover. |
| m5 | `app/modules/pessoal/calcula_rescisao.py` | Modela só aviso **indenizado**; a projeção do aviso indenizado para **+1 avo** de 13º/férias (Súmula 305 TST) depende do service. | Garantir projeção no service; documentar contrato. |
| m6 | `app/modules/pessoal/calcula_distribuicao.py:118` | Excedente de lucro tributado via IRRF retido mensal; o excesso ao limite isento é, em regra, tributável no **ajuste anual (DIRPF)** — a retenção na fonte é aproximação que pode divergir. | Revisar tratamento com contador; rotular como estimativa. |
| m7 | `app/modules/pessoal/calcula_ferias.py` | IRRF de férias isolado; pagas no mesmo mês do salário, as bases deveriam somar (IN RFB 1.500 art. 64). | Combinar bases quando no mesmo mês. |
| m8 | `app/modules/empresa/cnpj.py:29` | Não suporta o **CNPJ alfanumérico** (vigência jul/2026). `isdigit()` aceita dígitos unicode exóticos. | Planejar suporte alfanumérico; trocar `isdigit()` por filtro `0-9`. |

---

## ✅ O que está CORRETO (conferido valor a valor)

- **DAS Simples Nacional** (`calcula_das.py`): fórmula da alíquota efetiva `(RBT12×nominal − dedução)/RBT12`, Fator R (≥28%), multi-anexo, teto R$4,8M e sublimite R$3,6M — corretos. As **30 faixas da CGSN 140/2018 batem 100%** (5 anexos × 6 faixas conferidos em `0002`).
- **INSS escalonado** (`calcula_inss.py`): método correto (fatia por faixa), teto aplicado; faixas **2024 e 2025 corretas**.
- **IRPJ LP** (`calcula_irpj.py`): presunção, adicional de 10% sobre excedente proporcional aos meses, **quantização única no fim** (alinha com PVA), compensação de IRRF — corretos.
- **Presunção LP** (`0019`): os 8 grupos (1,6% / 8% / 16% / 32%) batem com IN RFB 1.700/2017.
- **FGTS** (`calcula_fgts.py`) e **PIS/Cofins cumulativo** (`calcula_pis_cofins.py`): corretos.
- **Rescisão** (`calcula_rescisao.py`): incidências tributárias certas — aviso indenizado isento de INSS/IRRF mas com FGTS; férias indenizadas + 1/3 isentas; multas FGTS 40%/20%.
- **13º** (`calcula_13o.py`): IRRF exclusivo na fonte + INSS em incidência separada — corretos.
- **CBS/IBS** (`calcula_cbs_ibs.py`): bem rotulado como estimativa; validações sólidas (NaN/inf/negativo).
- **CNPJ/CPF** (`cnpj.py`): algoritmo oficial dos 2 dígitos, rejeita sequências repetidas.
- **Disciplina transversal:** `Decimal` + `ROUND_HALF_EVEN` em tudo, **zero `float`**; SCD Type 2 em todas as tabelas; RLS nas tabelas de domínio. Princípios §8.1–§8.4 honrados no código.

---

## Anexo — Inventário auditado

**Algoritmos lidos:** `calcula_das`, `calcula_inss`, `calcula_irrf`, `calcula_fgts`, `calcula_irpj`, `calcula_csll`, `calcula_pis_cofins`, `calcula_icms`, `calcula_selic`, `calcula_rescisao`, `calcula_13o`, `calcula_ferias`, `calcula_prolabore`, `calcula_distribuicao`, `calcula_cbs_ibs`, `cnpj`.

**Seeds lidos:** `0002` (Simples Nacional), `0016` (INSS/IRRF/FGTS 2025), `0045` (INSS 2024), `0019` (presunção LP).

**Service/golden lidos:** `multa_juros/service.py`, `tests/unit/multa_juros/test_selic_mora.py`.
