---
tags: [adr, reforma-tributaria, cbs, ibs, sprint-14, fase-3]
fonte: "[[PlanoBackend]] §11 (Sprint 14) + LC 214/2025"
status: accepted
data: 2026-05-22
---

# ADR 0016 — Reforma Tributária: CBS/IBS informacional via SCD própria + simulador com 3 cenários

## Status

accepted (2026-05-22)

## Contexto

A LC 214/2025 institui CBS (federal, substitui PIS+Cofins) e IBS (estadual+municipal, substitui ICMS+ISS), com cronograma:

- **2026** — cobrança-teste informativa (CBS 0,9% + IBS 0,1% = 1,0% sobre a base; coexistem com PIS/Cofins/ICMS/ISS sem recolhimento separado).
- **2027-2032** — CBS plena substitui PIS+Cofins; IBS continua em teste; ICMS+ISS reduzem.
- **2033+** — regime pleno (alíquota de referência preliminar 26,5%, art. 156-A §1º).

A Sprint 14 (Fase 3) precisa entregar:
1. Cálculo CBS/IBS informacional 2026 (camada determinística).
2. Suporte aos campos `vCBS`/`vIBS`/`cClassTrib` no parser NF-e 4.x.
3. Simulador de impacto da Reforma.

Decisões de design avaliadas:

1. **Constante hardcoded** para alíquotas — simples mas viola §8.3 (SCD obrigatório); muda toda vez que regulamentação evolui.
2. **Reusar `aliquota_icms_uf`** com tipo='cbs' — viola separação semântica (CBS é federal, não estadual; reuso forçado).
3. **Tabela SCD própria `aliquota_cbs_ibs`** com trigger genérico (`scd_close_previous_valid_to` da migration 0025), seed das 3 fases + lookup por especificidade (regime/cnae/classificação LC 214 art. 9º).

Para o simulador 2033, considerei: (a) constante 26,5% hardcoded labelada "estimativa"; (b) SCD da própria `aliquota_cbs_ibs` com vigência 2033-01-01 + cenários ±2pp; (c) adiar simulador para sprint futura.

## Decisão

**Adotar (opção 3 + b):** tabela SCD própria + simulador com 3 cenários (pessimista/realista/otimista ±2pp em torno da alíquota da SCD).

Justificativas:

- **Princípio §8.3 cravado no DB** — vigências 2026/2027/2033 viram linhas SCD; trigger fecha `valid_to` da anterior automaticamente; REVOKE UPDATE/DELETE FROM PUBLIC + GRANT INSERT TO `tax_table_admin` (role criado na migration 0025) garantem append-only.
- **Cenários ±2pp** capturam a incerteza da regulamentação final do Comitê Gestor IBS sem hardcoded de "carga 26,5%" no algoritmo. Quando o PLP 68/2024 for sancionado e o Comitê publicar percentuais finais, basta uma nova vigência SCD para ajustar; cenários continuam derivados.
- **Lookup por especificidade** (regime → classificacao_lc214 → cnae_pattern com peso por comprimento do prefixo) prepara o terreno para diferenciação 60% (educação/saúde/transporte), 30% (serviços liberais regulamentados) e regime diferenciado (combustíveis/financeiras), sem alterar o algoritmo `calcula_cbs_ibs` quando essas vigências forem seedadas.
- **`observacao_estimativa` obrigatória em todo schema de saída** (§8.12) — label "Estimativa — sujeita a regulamentação (LC 214/2025 + PLP 68/2024 em tramitação)" propagada do algoritmo puro até o JSON do endpoint.

## Consequências

**Positivas:**

- A camada determinística da Sprint 14 fica isolada (`app/modules/reforma/`) e não atravessa as 28 module-boundaries existentes — risco de regressão baixo. Suite passa de 1199 → 1288 (+89 testes).
- Backfill informacional via worker idempotente (`reforma.refresh_cbs_ibs_historico`, diário às 04:30) garante que NF-e 4.0 antiga (sem extensão IBSCBSTot) recebe `valor_cbs`/`valor_ibs` calculados sem intervenção manual.
- Quando o Comitê Gestor IBS publicar alíquotas finais por UF/CNAE, expandir a SCD com `uf VARCHAR(2)` é trivial (migration 0036+ aditiva); o repo já suporta `cnae` no scoring.
- Frontend pode consumir `/v1/empresas/{eid}/reforma/simulacao` em 4 chamadas (1 GET) para mostrar 3 cenários comparativos + impacto de fluxo de caixa do split payment 2027.

**Negativas:**

- Cenários ±2pp são arbitrários — não há base estatística para ±2pp especificamente. Trade-off aceito: o objetivo do simulador é educacional (mostrar a faixa de incerteza), não previsão precisa. Documentado em `observacao_estimativa`.
- A repartição CBS/IBS no pleno (8,8% + 17,7%) é preliminar e não bate exatamente com a discussão do Comitê Gestor (que cogita IBS por UF). Aceito como aproximação enquanto o split por UF não está regulamentado.
- `documento_fiscal.valor_cbs`/`valor_ibs` agora podem ser populados via 2 caminhos (XML 4.x ou backfill informacional). O helper `popular_cbs_ibs_informacional` preserva XML quando ambos os campos já estão NOT NULL (§8.2) — mas não há flag para distinguir "vindo do XML" vs "calculado informacional". Aceito como pendência consciente.

## Pendências derivadas

- [[pendencias/reforma-cbs-ibs-emissao-nfse]] — Focus NFe ainda não documenta API de CBS/IBS para todos os municípios; flag `FOCUS_NFSE_ENVIA_CBS_IBS=False` permanece até liberação.
- [[pendencias/reforma-aliquota-ibs-por-uf]] — expandir SCD com `uf` quando o Comitê Gestor IBS publicar percentuais por UF.
- Imposto Seletivo (IS) sobre bens nocivos — out-of-scope MVP (§11 Fase 5 backlog).
- Split payment real 2027 — Sprint da Fase 5.
- Bloco K do SPED com CBS/IBS — Sprint 17.
- NFC-e/CT-e/MDF-e com CBS/IBS — pendência (parser desta sprint só cobre NF-e 55).

## Relacionado

- Modulo: [[modulos/reforma]]
- Sprint: [[sprints/sprint-14-reforma]]
- Princípios: [[principios/03-scd-type-2]], [[principios/08-llm-nao-escreve-fatos]], [[principios/12-estimativa-labelada]]
- ADRs upstream: ADR 0005 (fatos imutáveis), ADR 0014 (PGDAS via procuração)
