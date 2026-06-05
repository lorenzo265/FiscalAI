---
titulo: Seed RAT/SAT + Terceiros/Sistema S por CNAE/grau de risco — provisão de encargos patronais
status: aberta
severidade: MAJOR (subprovisão de passivo trabalhista em LP/LR/SN-IV)
origem: AUDITORIA_FISCAL_BACKEND.md · issue M8 (FA5, 2026-06-04)
data: 2026-06-04
decisao: parametrização entregue — seed por CNAE fica como follow-up (não fabricar por CNAE)
---

# M8 — Seed RAT/SAT + Terceiros por CNAE/grau de risco

## Problema (contexto)

`provisoes/calcula_provisao.py` hardcodava `_ALIQ_INSS_PATRONAL = 0.20` (CPP base).
O fix FA5 (2026-06-04) parametrizou a alíquota via `aliquota_patronal_regime()` e
adicionou `rat_sat` e `aliquota_terceiros` ao payload `GerarProvisaoIn`.

**O que ainda falta:** RAT/SAT (Lei 8.212/91 art. 22 II) e Terceiros/Sistema S variam
por **CNAE** e por **grau de risco da atividade**. Enquanto o seed por CNAE não
existir, `GerarProvisaoIn.rat_sat` e `GerarProvisaoIn.aliquota_terceiros` ficam com
default 0% — ou seja, o encargo patronal provisionado para LP/LR/SN-IV é só a CPP
20% (piso conservador).

Subprovisão típica:

| Componente   | Valor típico | Base legal                          |
|--------------|-------------|-------------------------------------|
| RAT/SAT      | 1–3% × FAP  | Lei 8.212/91 art. 22 II             |
| SENAI/SESI   | 1,0% + 1,5% | Dec-lei 4.048/42 + Dec-lei 9.403/46 |
| SEBRAE       | 0,3–0,6%    | Lei 8.029/90 art. 8º                |
| SESC/SENAC   | 1,5% + 1,0% | Dec-lei 9.853/46 + Dec-lei 8.621/46 |
| INCRA        | 0,2%        | Lei 2.613/55 art. 6º                |
| Salário-educ.| 2,5%        | Lei 9.766/98                        |
| **Terceiros total típico** | **~5,8%** | (varia por CNAE/atividade) |

Subprovisão total sem RAT+Terceiros: ~⅓ do passivo (27,8% correto vs. 20% piso).

## Por que está adiada

RAT é fixado **por empresa** (grau de risco) via Decreto 3.048/99 Anexo V + FAP anual
(Portaria MPS/RFB — emitida até nov de cada ano para o ano seguinte). Terceiros variam
por CNAE 2-digit (tabela publicada no site da Receita Federal — "Terceiros por CNAE").

Fabricar valores por CNAE sem a fonte oficial violaria o §8 (LLM nunca escreve fatos;
SCD Type 2 — alíquota sempre de norma vigente). O contador conhece os valores da empresa
e **pode informar via `rat_sat` + `aliquota_terceiros`** no payload — isso está entregue.

## O que falta para fechar

### Opção A — Seed por tabela de Terceiros (menor esforço, maior cobertura)

1. Baixar a **tabela de Terceiros por CNAE** do site RFB (Instrução Normativa SRF vigente
   + atualizações anuais) — tabela pública com alíquota por CNAE 2-digit.
2. Criar migration SCD: tabela `aliquota_terceiros_cnae` com
   `(cnae_2_digitos, aliquota, valid_from, valid_to)` + RLS se por tenant, ou tabela
   pública se for referência nacional.
3. Expor endpoint/helper no service de provisões para lookup por CNAE da empresa.
4. Atualizar `ProvisoesService.gerar_provisao_mensal` para usar o lookup se
   `payload.aliquota_terceiros == 0` (zero = "não informado explicitamente").

### Opção B — Grau de risco RAT por empresa (maior precisão, requer input do contador)

1. Adicionar campo `grau_risco_rat` (`Decimal(5,4)`) na tabela `empresa`
   (ex.: `0.01` para leve, `0.02` médio, `0.03` grave) via migration SCD.
2. FAP: multiplicador anual (0,5 a 2,0) — receber como input do contador ou
   via integração futura com e-CAC.
3. `aliquota_patronal_regime()` recebe `rat_sat = grau_risco × fap` do service.

## Gatilho para abrir

O contador informa RAT/grau de risco ou o CNAE da empresa já está cadastrado
(`empresa.cnae_principal`) → o seed de Terceiros por CNAE pode ser lido automaticamente
sem precisar de input manual.

## Estado atual (piso conservador entregue)

- `GerarProvisaoIn.rat_sat = 0` → provisão usa só CPP 20% (piso legal documentado).
- `GerarProvisaoIn.aliquota_terceiros = 0` → Terceiros não provisionados.
- Quando o contador informa os valores corretos via API, a provisão é **precisa**.
- Goldens: `TestGoldenLPComRatTerceiros` prova 27,8% (RAT 2% + Terceiros 5,8%).

Relacionado: [[03-scd-type-2]] · [[01-rls-multi-tenant]] · interage com
`provisoes/calcula_provisao.py`, `provisoes/service.py`, `provisoes/schemas.py`.
