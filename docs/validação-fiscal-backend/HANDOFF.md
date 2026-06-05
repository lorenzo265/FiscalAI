# HANDOFF — Remediação da Auditoria Fiscal (2026-06-04)

> **Append-only.** Cada agente acrescenta um bloco ao terminar:
> **data · agente (FA-N) · o que fez · arquivos · testes (delta) · ALGORITMO_VERSAO · pendências · próximo.**
> Relatório completo (17 issues) em `AUDITORIA_FISCAL_BACKEND.md` (Parte 1 = C1, M2–M5; Parte 2 = M6–M9, m1–m8).

---

## Fase 0 — Auditoria + completude (2026-06-04 · orquestrador claude-opus-4-8)

**O que fez:** leu o relatório original (5 de 14 issues documentadas), rodou 2 auditorias de completude
de contexto fresco (tributos-core + folha/relatórios) sobre os 30 `calcula_*.py` + seeds. Recuperou
**12 issues novas** (M6–M9 majors, m1–m8 minors) e completou `AUDITORIA_FISCAL_BACKEND.md` (Parte 2).
Conjunto consolidado: **17 issues**.

**Decisões do orquestrador:**
- **C1 (SELIC):** confirmado que a auditoria está correta (metodologia Sicalc — juros, inclusive o 1%
  do mês de pagamento, só a partir do mês subsequente ao vencimento). O revisor do sprint anterior
  errou ao validar o 1% como sempre-incidente. **Corrigir** + reescrever o golden que trava o bug.
- **M2 (tabelas 2026):** **ADIADO por decisão do usuário** — não seedar tabela tributária sem norma
  oficial (fabricar alíquota viola §3 e geraria folha errada). Mantida como pendência ativa →
  `docs/pendencias/tabelas-tributarias-2026.md`.
- **M8 (provisão encargos):** corrigir por **parametrização regime-aware** (sem fabricar RAT por CNAE);
  seed real de RAT/FAP/Terceiros é follow-up documentado.
- **M6, M7:** corrigíveis agora — alíquotas/datas são **estatutárias** (Lei 9.249 art.15; EC 132/cronograma
  da transição), não dependem de Portaria temporal.

**Plano de remediação (Sonnet, sequencial, 1 review por lote):**
| Lote | Issues | Escopo |
|---|---|---|
| FA1 | C1 | `multa_juros/calcula_selic.py` + golden |
| FA2 | M4, M5 | `pessoal/calcula_irrf.py` + propagação férias/13º/rescisão |
| FA3 | M3, M6 | `lucro_presumido/calcula_csll.py` + seed presunção (migration) + repo |
| FA4 | M7 | `reforma` — migration corrige `valid_to` CBS/IBS + teste SCD |
| FA5 | M8 | `provisoes/calcula_provisao.py` — parametrização regime-aware |
| FA6 | M9 | `relatorios/calcula_dre.py` — ROB só `4.1`, `4.9` separado |
| FA7 | m1, m2, m3 | `reinf` + seed ICMS + `lucro_presumido/calcula_pis_cofins.py` |
| FA8 | m4, m5, m6, m7, m8 | `pessoal` (hora_extra, distribuicao, prolabore, calcula_13o) |

**Pendência registrada:** M2 → `docs/pendencias/tabelas-tributarias-2026.md` (ativa, aguarda norma).

**Próximo:** FA1 (C1 SELIC — crítico).

---

## Fase 1 — Remediação (lotes FA-N)

<!-- Cada agente implementador acrescenta seu bloco abaixo, em ordem. -->

---

### FA1 — C1 SELIC mesmo mês (2026-06-04 · agente Sonnet)

**O que mudou:**

Antes (v1 — bugado):
```python
# Aplica-se sempre que há atraso (mesmo se pagamento no mesmo mês do vencimento)
acrescimo_mes = (valor * Decimal("0.01")).quantize(...)
```

Depois (v2 — correto):
```python
pagamento_mes_1 = date(data_pagamento.year, data_pagamento.month, 1)
vencimento_mes_1 = date(data_vencimento.year, data_vencimento.month, 1)
if pagamento_mes_1 > vencimento_mes_1:
    acrescimo_mes = (valor * Decimal("0.01")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )
else:
    # Mesmo mês: sem juros (1% nem SELIC — não há mês subsequente fechado)
    acrescimo_mes = Decimal("0")
```

A SELIC acumulada (`aliquota_selic_acumulada`) já era correta: o loop `while mes_iter < pagamento_mes_atual` nunca executa quando pagamento e vencimento são do mesmo mês, produzindo `juros_selic = 0`. Só `acrescimo_mes` precisava do guard.

**Base legal:** Lei 9.430/1996 art. 61 §3º + metodologia Sicalc — juros de mora (SELIC acumulada + 1% do mês de pagamento) incidem apenas a partir do 1º dia do mês subsequente ao vencimento. Pagamento dentro do mesmo mês → apenas multa de mora (0,33%/dia, teto 20%); juros = 0.

**Gabarito numérico (exemplo confirmável no Sicalc):**

| Cenário | Vence | Paga | Dias | Multa | SELIC | Acréscimo 1% | Total acréscimos | Valor atualizado |
|---|---|---|---|---|---|---|---|---|
| Mesmo mês (antes = errado, agora correto) | 20/05/2025 | 25/05/2025 | 5 | R$16,50 | R$0,00 | **R$0,00** | R$16,50 | R$1.016,50 |
| Mês subsequente (guard distingue) | 20/05/2025 | 10/06/2025 | 21 | R$69,30 | R$0,00 | **R$10,00** | R$79,30 | R$1.079,30 |

(Base: principal R$1.000,00; SELIC = 0 meses cheios nos dois casos pois mês seguinte ao venc = jun = mês do pagamento nos dois exemplos; diferença é só no 1% fixo.)

**Goldens reescritos/adicionados:**

- `test_multa_5_dias_dentro_mesmo_mes`: antes assertia `acrescimo_mes_pagamento == Decimal("10.00")` e `valor_atualizado == Decimal("1026.50")` (ERRADO — protegia o bug). Agora assere `acrescimo_mes_pagamento == Decimal("0.00")`, `total_acrescimos == Decimal("16.50")`, `valor_atualizado == Decimal("1016.50")`.
- `test_acrescimo_mes_incide_em_mes_subsequente` (**novo**): prova que para pagamento em mês subsequente (20/mai → 10/jun) o 1% incide (`acrescimo_mes_pagamento == Decimal("10.00")`), distinguindo os dois lados do guard.
- `test_algoritmo_versao_presente_no_resultado`: assert `"mora.sicalc.v1"` → `"mora.sicalc.v2"`.

**ALGORITMO_VERSAO:** `mora.sicalc.v1` → `mora.sicalc.v2` (lógica de juros modificada — incompatível com v1).

**Arquivos tocados:**
- `app/modules/multa_juros/calcula_selic.py` — guard mês subsequente + ALGORITMO_VERSAO bump
- `tests/unit/multa_juros/test_selic_mora.py` — reescrita de 1 golden + 1 golden novo + versão bump

**Testes:**
- Delta: +1 golden novo (`test_acrescimo_mes_incide_em_mes_subsequente`)
- Contagem final módulo `multa_juros`: **30 passed** (era 28 + 1 reescrito + 1 novo = 30 passou)
- mypy `app/modules/multa_juros`: **Success: no issues found in 6 source files**
- Efeito colateral: nenhum outro teste quebrou. `calcular_denuncia_espontanea` propaga automaticamente via `calcular_mora` — já corrigido.

**Pendências:** nenhuma para C1. Confirmar contra simulação real Sicalc (instrução da auditoria) antes de mergear em produção — gabarito acima confere com a regra legal, mas validação no portal é recomendada.

**Próximo:** FA2 — M4 (`pessoal/calcula_irrf.py`: pensão alimentícia) + M5 (desconto simplificado mensal).

> **Nota de consolidação (orquestrador):** os blocos FA2–FA8 abaixo foram reconsolidados aqui a
> partir dos relatórios dos agentes. Os agentes FA2–FA8 gravaram, por engano, num caminho relativo
> (`docs/...` a partir de `analista-fiscal-api/`) — o stray foi mesclado e removido. As mudanças de
> **código** ficaram no lugar certo (paths `app/...` são relativos à raiz do api); só o write-back do
> handoff precisou de merge.

---

### FA2 — IRRF M4 (pensão) + M5 (desconto simplificado) (2026-06-04 · agente Sonnet)
- **M4 pensão alimentícia (Lei 9.250/95 art.4º II/art.8º II "f"):** novo param `pensao_alimenticia: Decimal = 0` em `calcular_irrf_mensal`, deduzido da base (método legal). Backward-compat.
- **M5 desconto simplificado mensal (Lei 14.848/2024):** calcula os 2 métodos e devolve `min(legal, simplificado)`. `desconto_simplificado = 0,25 × teto da 1ª faixa`, **derivado da SCD `FaixaIrrf`** (não hardcoded; ≈ R$564,80). Novos campos `metodo: 'legal'|'simplificado'` e `pensao_alimenticia` em `ResultadoIrrf`.
- **Goldens:** 13 casos caíram de valor **legitimamente** (simplificado é mais benéfico p/ salários PME — ex.: sal 3.000 → IRRF 36,55→13,20). Casos de alta renda / muitos dependentes seguem no `legal`.
- **ALGORITMO_VERSAO:** `irrf.mensal.v2`. **Testes:** pessoal 216 passed (+10). mypy ok.
- **Pendência:** `calcula_ferias/13o/rescisao` ainda não expõem `pensao_alimenticia` na própria assinatura (default 0). **Próximo:** FA3.

### FA3 — CSLL compensação (M3) + presunção saúde (M6) (2026-06-04 · agente Sonnet)
- **M3 CSLL deduz CSRF retida:** novo param `csll_a_compensar: Decimal = 0` simétrico ao `irrf_a_compensar` do IRPJ; novos campos `csll_a_compensar`/`csll_consumida`/`csll_saldo_credor`/`csll_a_recolher`. `csll_a_recolher = max(0, devida − compensar)`; excedente vira saldo credor. Service passa o valor (mesma origem do IRPJ). Ex.: receita 300k×32%×9%=8.640 devida − 3.000 PCC = **5.640 a recolher**. `csll.v2`.
- **M6 presunção saúde:** **migration `0053`** insere 9 patterns CNAE a 32%/32% (`862/863/864/865/866/869` saúde não-hospitalar, `75` vet, `855` cursos, `96` serviços pessoais) na mesma vigência SCD (1996-01-01). Confirmado **CNAE 8630 → 32%** (era 8% por omissão); 8610 (hospitais) e comércio inalterados.
- **Testes:** lucro_presumido 143 passed (+14). mypy ok. **Próximo:** FA4.

### FA4 — Reforma SCD CBS/IBS valid_to (M7) (2026-06-04 · agente Sonnet)
- **Migration `0054`** fecha as vigências sobrepostas: `teste_2026`→`valid_to=2026-12-31`, `transicao_2027_2032`→`2032-12-31`, `regime_pleno_2033`→`NULL`. Cobertura contínua, sem overlap/gap. `valid_from`/alíquotas intactos (§8.3).
- **Trigger não alterado** (decisão): `scd_close_previous_valid_to` é compartilhado com outras tabelas SCD onde a chave por-`fase` é correta; fechamento explícito por seed é o certo p/ as 3 fases estatutárias. Documentado no migration.
- **Testes:** reforma 110 passed (+27, incl. teste de higiene SCD provando 1 vigência por data). mypy ok. **Próximo:** FA5.

### FA5 — Provisão encargos regime-aware (M8) (2026-06-04 · agente Sonnet)
- **Regra regime-aware** (nova helper `aliquota_patronal_regime`): MEI e **SN Anexos I/II/III/V → 0%** (CPP no DAS, evita dupla contagem); **SN Anexo IV / LP / Lucro Real → 20% + RAT×FAP + Terceiros**. `calcular_provisoes` recebe `aliquota_inss_patronal`; service resolve por regime/anexo.
- **RAT/Terceiros parametrizados, não fabricados:** `GerarProvisaoIn` ganhou `rat_sat`/`aliquota_terceiros` (default 0 = piso 20% conservador). Seed real por CNAE/grau de risco → **pendência `docs/pendencias/rat-fap-terceiros-seed.md`**.
- **Golden enganoso reescrito** (`test_folha_10k_lp` assertia 222,22 como "correto LP" → agora documentado como piso 20%; novos goldens c/ 27,8% = 308,89 e SN desonerado = 0). `prov-2026.08`.
- **Testes:** provisoes 52 passed (+18). mypy ok. **Flag p/ UX:** SN Anexo IV sem `anexo_simples` cadastrado cai em 0% (conservador). **Próximo:** FA6.

### FA6 — DRE Outras Receitas fora da ROB (M9) (2026-06-04 · agente Sonnet)
- **Receita Operacional Bruta agora soma só `4.1`** (não todo `4.*`). `4.9 Outras Receitas` vira **linha separada** somada abaixo do EBIT, no LAIR (Lei 6.404 art.187). Novo campo `outras_receitas` em `ResultadoDre`.
- Resultado final (LAIR/Lucro Líquido) **idêntico**; o que muda é ROB/Receita Líquida/margens/Giro, antes infladas por `4.9.x`. Propaga p/ `dre_aux_lp` e `calcula_indicadores` automaticamente.
- **ALGORITMO_VERSAO:** `dre.estruturada.v2`. **Testes:** relatorios 56 passed (+14). mypy ok. **Próximo:** FA7.

### FA7 — minors tributários m1/m2/m3 (2026-06-04 · agente Sonnet)
- **m1 REINF:** fix conservador (sem mudar lógica) — comentário "IRRF sem limite mínimo" corrigido (há piso DARF R$10 por acumulação mensal, tratado no recolhimento, não na nota). +3 testes documentais. `reinf.retencao_pj.v1` (sem bump).
- **m2 ICMS-RJ — Opção A:** FECP separado. `interna` 0,20→**0,18** + `fecp` 0,02 (**migration `0055`**); `calcula_icms.py` passa a usar **efetiva = interna + fecp** (RJ continua **20% efetivo** — provado por golden antes/depois). FECP deixa de ser campo morto. `icms.mensal.v2`. Demais UFs revisadas, sem alteração.
- **m3 PIS/Cofins:** `base = max(0, receita − exclusoes)` (não mais `ValueError`); excedente vira `saldo_exclusao_transportar` (carryover p/ mês seguinte). `pis/cofins.v2`.
- **Testes:** reinf 13 + icms 22 + lucro_presumido 149. mypy ok. **Próximo:** FA8.

### FA8 — minors de folha m4/m5/m6/m7/m8 (2026-06-04 · agente Sonnet)
- **m4 adicional noturno:** hora noturna reduzida (52'30", CLT art.73 §1º) — fator `60/52,5`. Ex.: 10h reais → 11,4286h equiv. → adicional R$22,86 (era R$20,00, ~14% a menos). Novo campo `horas_noturnas_reduzidas`. `hora_extra.v2`.
- **m5 DSR:** doc-only — `ResultadoHoraExtra` marcado como **valor parcial** (sem reflexo DSR, Súmula 172 TST); implementação completa = sprint dedicada.
- **m6 distribuição:** `valor_tributavel` quantizado (2 casas) antes do IRRF. `distribuicao.v2`.
- **m7 pró-labore:** docstring stale (`189,59`) removida; refere à SCD `deducao_dependente`. (doc-only)
- **m8 13º:** `_validar_avos` aceita `[0,12]`; `avos=0` → resultado zero (uniforme com rescisão; Dec. 57.155/65). `13o.v3`.
- **Testes:** pessoal 228 passed (+12). mypy ok. **Pendência:** DSR completo (m5); propagar `horas_noturnas_reduzidas` no holerite. **Próximo:** fechamento/orquestrador.

---

## Fase 2 — Fechamento (2026-06-05 · orquestrador claude-opus-4-8)

**Verificação final (venv reconstruído limpo):**
- Suite completa: **2433 passed / 0 failed / 3 skipped** (skips: symlink storage OS + 2× eval_live).
  Baseline pré-validação fiscal: 2318 → **+115 testes**.
- mypy strict: **0 erros em 356 arquivos**. `import app.main`: OK.
- Alembic: **head único `0055`**, chain linear `0050→0051→0052→0053→0054→0055`.

**2 regressões/defeitos pegos no gate final e corrigidos pelo orquestrador:**
1. `tests/unit/sped/test_ecd_service.py` — fixture construía `ResultadoDre` sem o campo novo
   `outras_receitas` (FA6 rodou só `tests/unit/relatorios`, não pegou o teste cross-módulo de SPED).
   Corrigido (8 erros → 0).
2. `alembic/versions/0052_sprint20_pr1_darf_lp.py` — **defeito pré-existente** (sem `revision`/
   `down_revision`) que quebrava toda a chain alembic; adicionadas as variáveis. Agora head único.

**Status das 17 issues:**
- 🔴 C1 → FA1 ✅ · 🟠 M3,M4,M5 → FA2/FA3 ✅ · M6,M7,M8,M9 (recuperados) → FA3/FA4/FA5/FA6 ✅
- 🟡 m1–m8 → FA7/FA8 ✅
- **M2 (tabelas 2026):** ADIADA por decisão do usuário → `docs/pendencias/tabelas-tributarias-2026.md`.

**Pendências conscientes criadas:** `tabelas-tributarias-2026.md` (M2), `rat-fap-terceiros-seed.md` (M8).
Follow-ups menores anotados nos blocos FA (acumulação IRRF/DARF, carryover PIS/Cofins, DSR, SN Anexo IV).

**Migrations novas:** 0053 (presunção saúde), 0054 (reforma valid_to), 0055 (ICMS-RJ FECP).
**Write-back:** `log_agente.md` atualizado (2433 + seção Validação Fiscal). **Nada commitado** —
aguarda decisão do usuário. Stray `analista-fiscal-api/docs/validação-fiscal-backend/` mesclado e removido.
