# Quick-Fixes — Críticos corrigíveis a partir de hoje
**Origem:** `auto-de-infracao-2026-06-21.md` · **Data:** 2026-06-21

> Os 7 🔴 em ordem de dor. Cada um com o arquivo, a causa-raiz e a correção mínima. **Toda mudança de alíquota/tabela passa pelo fluxo `/atualizar-aliquota` (PROPOR + GATE humano) — não aplicar cego.**

---

## 1. 🔴 IRRF sem o redutor da Lei 15.270/2025 — *corrigir PRIMEIRO*
**Arquivos:** `app/modules/pessoal/calcula_irrf.py` · `alembic/versions/0016_sprint10_pessoal_tabelas.py:435-462`
**Causa:** tabela `tabela_irrf_faixa` só tem vigência `2024-02-01 → NULL`; o algoritmo aplica só a progressiva tradicional. Desde 01/2026 a Lei 15.270/2025 dá **isenção efetiva até R$ 5.000/mês** e **redução gradual até R$ 7.350**.
**Correção:**
1. Nova vigência SCD `valid_from=2026-01-01` (via `aliquota-smith` / `/atualizar-aliquota`) — tabela progressiva mantida (0;7,5;15;22,5;27,5%), dedução por dependente **R$ 189,59**, simplificada anual **R$ 17.640,00**.
2. **Mecanismo novo** (não é só INSERT): aplicar o **redutor pós-cálculo**. Faixa intermediária R$ 5.000,01–7.350,00: `redutor = 978,62 − (0,133145 × rendimento_tributável)`, subtraído do IRRF tradicional (piso 0). Acima de R$ 7.350: tabela cheia.
3. Golden de borda: R$ 5.000,00 (IRRF≈0) · R$ 5.000,01 · R$ 7.350,00 · R$ 7.350,01 (tabela cheia).
**Fonte:** Lei 15.270/2025 (sancionada 26/11/2025, efeitos 01/01/2026) — confirmada na web jun/2026.

## 2. 🔴 Distribuição de lucros sem retenção de 10%
**Arquivo:** `app/modules/pessoal/calcula_distribuicao.py:73-140`
**Causa:** trata só isenção + IRRF progressivo; não há retenção de 10% na fonte.
**Correção:** reter **10%** sobre o total pago/creditado quando a soma do mês da **mesma PJ → mesma PF** for **superior a R$ 50.000** (igual a 50.000 não retém). Sem deduções na base. Aplica-se **inclusive ao Simples Nacional**. Recalcular sobre o acumulado do mês se houver vários pagamentos. Preservar isenção de lucros apurados até 2025/aprovados até 31/12/2025.
**Golden de borda:** R$ 50.000,00 (não retém) · R$ 50.000,01 (retém 10%) · dois pagamentos no mês somando >R$50k.
**Fonte:** Lei 15.270/2025 — confirmada na web (posição oficial RFB, inclusive SN).

## 3. 🔴 Fator R sem encargos
**Arquivo:** `app/modules/fiscal/service.py:106`
**Causa:** `fator_r = folha_12m / rbt12` — numerador sem CPP/FGTS/13º.
**Correção:** `fator_r = (folha_12m + encargos_12m) / rbt12`, onde a massa salarial inclui salários, pró-labore, **CPP + FGTS** e 13º (Res. CGSN 140/2018 art. 26 §1º). Unificar a definição de "folha" usada aqui, no PGDAS (#4) e no domínio de folha (A2) — hoje divergem.
**Golden:** montar o numerador a partir de `(folha+encargos)` e testar a virada Anexo III↔V em 28,00%.

## 4. 🔴 PGDAS transmite folha vazia ao SERPRO
**Arquivo:** `app/modules/pgdas/service.py:285-298`
**Causa:** `"folhasSalario": []` fixo, mesmo p/ Anexo III/V → SERPRO recalcula o Fator R sem folha → resolve Anexo V → DAS divergente do interno.
**Correção:** preencher `folhasSalario` com a folha 12m discriminada (a mesma do #3). Golden cruzando "DAS calculado internamente" == "DAS que o payload produziria".

## 5. 🔴 DRE conta IRPJ/CSLL (e financeiro) duas vezes
**Arquivo:** `app/modules/relatorios/calcula_dre.py:244-252`
**Causa:** "Outras Despesas Operacionais" = `_somar_prefixo("5", excluir=…)` captura **5.2 Financeiras** e **5.3 Provisão IRPJ/CSLL** dentro do EBITDA/EBIT.
**Correção:** excluir os prefixos 5.2 e 5.3 das despesas operacionais; resultado financeiro só via `resultado_financeiro` (após EBIT); IRPJ/CSLL só via `irpj_csll_apurado`.
**Golden:** DRE com saldo em 5.2.01 (juros) e 5.3.01 (provisão) — provar que não há dupla contagem.

## 6. 🔴 Lançador automático sem validar partida dobrada
**Arquivo:** `app/modules/contabil/lancador_service.py:593-633`
**Causa:** `_persistir` grava `total_debito=total_credito=candidato.total` sem rodar `validar_partidas` nem comparar Σ-débitos × Σ-créditos nem rejeitar valor 0.
**Correção:** antes de persistir, exigir Σ-D == Σ-C (tolerância R$0,01) e todo valor > 0 — mesma trava do `criar_lancamento_manual`. Rejeitar líquido negativo / partida valor=0.
**Golden:** candidato desbalanceado, valor 0 e folha com líquido negativo devem ser **rejeitados**.

## 7. 🟠 (alto impacto) FGTS no dia 7 — deveria ser dia 20
**Arquivo:** `app/modules/agenda/gerar_calendario.py:243-250`
**Causa:** gera FGTS no dia 7 citando texto revogado (Lei 8.036/1990 art.15 §5º).
**Correção:** `dia_vencimento = 20` (Lei 14.438/2022 + FGTS Digital, competências desde mar/2024). **Atenção à direção do dia não-útil:** o FGTS **antecipa** para o dia útil anterior (≠ a postergação que `_proximo_dia_util` aplica às demais obrigações). Atualizar os 2 goldens que blindam o dia 7.
**Fonte:** Lei 14.438/2022 — confirmada na web.

---

### Notas de execução
- **#1, #2, #7** mexem em alíquota/prazo legal → fluxo `/atualizar-aliquota` com GATE humano antes do merge.
- **#3 e #4** são a mesma causa-raiz (definição de folha do Fator R) — corrigir juntos.
- **#5 e #6** são contábeis puros, sem tabela tributária — corrigíveis direto com golden novo.
- Rodar `pytest` + `mypy strict` em cada PR (critério de merge do projeto).
