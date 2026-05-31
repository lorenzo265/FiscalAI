---
tags: [pendencia, runbook, externo, reforma-tributaria, fase-3, fase-5]
fonte: "Sprint 19.8 (2026-05-29) — trilha 100% fechada"
status: ativo-aguardando-terceiro
atualizado: 2026-05-29
---

# 🛠️ Runbook — Ativação de pendências externas

> 6 pendências que dependem de terceiros publicarem leiautes,
> regulamentações ou APIs. Não vale implementar agora e esperar — vira
> código morto. Vira **runbook**: "quando X publicar, fazer Y" com
> checklist de PR pequeno.
>
> Princípio §8.11 (out-of-scope é declarado, não improvisado) +
> §8.12 (transmissão é ato consciente). Cada item tem trigger explícito,
> trabalho técnico estimado, arquivos a alterar e testes a adicionar.

**Status global:** Sprint 19.8 fechou a trilha 100% deixando esses
6 itens como `[externo-runbook]`. Nenhuma decisão de produto pendente.

## Índice

1. [#19 — Focus NFe CBS/IBS em NFS-e](#19--focus-nfe-cbsibs-em-nfs-e)
2. [#20 — Alíquotas IBS por UF/município](#20--alíquotas-ibs-por-ufmunicípio)
3. [#21 — Imposto Seletivo (IS)](#21--imposto-seletivo-is)
4. [#22 — Split payment real 2027](#22--split-payment-real-2027)
5. [#23 — Bloco K SPED com CBS/IBS](#23--bloco-k-sped-com-cbsibs)
6. [#24 — NFC-e/CT-e/MDF-e com CBS/IBS](#24--nfc-ect-emdf-e-com-cbsibs)

---

## #19 — Focus NFe CBS/IBS em NFS-e

**Trigger de ativação:** Focus NFe publica documentação oficial dos
campos CBS/IBS (`vCBS`, `vIBS`, `cClassTrib`) em NFS-e para todos os
municípios cobertos. Comunicado virá em https://focusnfe.com.br/blog/.

**Trabalho técnico** (~1-2 dias):

1. `app/config.py` — flip `FOCUS_NFSE_ENVIA_CBS_IBS=True` (default
   `False` desde Sprint 14 PR2).
2. `app/modules/notas/service.py::_montar_payload_focus_nfse` — verificar
   se já preenche `vCBS`/`vIBS`/`cClassTrib` quando flag é true (Sprint
   14 PR2 deixou hook pronto). Validar contra exemplos novos da Focus.
3. `tests/integration/notas/test_focus_nfse_sandbox.py` — adicionar
   teste que valida emissão com CBS/IBS no sandbox Focus.
4. Atualizar `log_agente.md` — marcar #19 como ✅ resolvida.

**Dependências:** Sprint 14 PR2 já entregou o cálculo CBS/IBS. Esta
ativação é só ligar o switch + validar Focus aceita o payload novo.

---

## #20 — Alíquotas IBS por UF/município

**Trigger de ativação:** Comitê Gestor IBS publica os percentuais
estaduais e municipais (lei estadual / lei municipal de cada ente
federativo). Acompanhar https://www.gov.br/fazenda/pt-br/composicao/
orgaos-vinculados/comite-gestor-ibs.

**Trabalho técnico** (~1 dia + seed contínuo via painel admin):

1. **Migration aditiva** em `aliquota_cbs_ibs`:
   ```python
   op.add_column("aliquota_cbs_ibs", sa.Column("uf", sa.CHAR(2), nullable=True))
   op.add_column("aliquota_cbs_ibs", sa.Column(
       "municipio_ibge", sa.String(7), nullable=True
   ))
   op.create_index(
       "ix_cbs_ibs_uf_mun", "aliquota_cbs_ibs",
       ["uf", "municipio_ibge"],
       postgresql_where="uf IS NOT NULL",
   )
   ```
2. `app/modules/reforma/aliquota_cbs_ibs_repo.py::_especificidade` —
   ampliar o score order para considerar `(uf, municipio)` ANTES de
   `(setor)` ANTES de `(default)`. Sprint 14 PR1 já estruturou para
   aceitar mais um nível.
3. **Seeds via painel admin Sprint 19.5** — cada UF emitirá uma
   sugestão de vigência (`POST /v1/admin/tabelas/cbs_ibs/vigencia`)
   conforme leis estaduais publicarem. Ao todo: 27 UFs × 2 (CBS+IBS)
   = 54 vigências iniciais; municípios entram ad-hoc.
4. Testes: `test_aliquota_repo_uf_municipio.py` — golden por UF,
   prevalência uf > setor > default.
5. Atualizar `log_agente.md` — marcar #20 como ✅ resolvida.

**Dependências:** zero — toda a infraestrutura (SCD Type 2 + repo
+ painel admin) já está pronta desde Sprint 14.

---

## #21 — Imposto Seletivo (IS)

**Trigger de ativação:** Lei Complementar 214/2025 art. 9º §6º
regulamentado (RFB define produtos/operações sujeitos: bebidas
alcoólicas, fumo, veículos poluentes, jogos/apostas, etc.).

**Trabalho técnico** (~5-7 dias — módulo novo):

1. Migration nova `0052_sprint_xx_imposto_seletivo.py` criando tabela
   `aliquota_imposto_seletivo` (SCD Type 2 com NCM + alíquota).
2. Novo módulo `app/modules/imposto_seletivo/`:
   * `calcula_imposto_seletivo.py` — função pura por NCM.
   * `repo.py` — leitura SCD.
   * `service.py` — orquestra com `ApuracaoFiscal`.
   * `router.py` — endpoint `POST /imposto-seletivo/calcular`.
3. Integrar em `documento_fiscal_item` (Sprint 18 PR1): adicionar
   campo `valor_imposto_seletivo NUMERIC(14,2)` opcional.
4. Geradores SPED: incluir IS nos blocos M/A/C do EFD-Contribuições e
   no bloco C do EFD ICMS-IPI conforme leiaute final publicado.
5. Testes: golden por NCM (cigarro, cerveja, gasolina, veículo poluente).
6. Atualizar `log_agente.md` + criar nota módulo em `docs/modulos/`.

**Dependências:** depende de #20 (estrutura SCD por UF/município já
pronta no `aliquota_cbs_ibs` — IS pode reusar padrão).

**Marco:** este é o último item de produto da Reforma Tributária.
Originalmente escopo Fase 5; antecipa se cliente regulado aparecer.

---

## #22 — Split payment real 2027

**Trigger de ativação:** BCB + PSPs (Stripe, Pagar.me, Cielo, Stone)
publicam fluxo técnico de retenção na transação (Pix/cartão). Marco
oficial: art. 60 LC 214/2025 — split começa 2027.

**Trabalho técnico** (~7-10 dias — integração com PSPs é não-trivial):

1. Decisão de arquitetura (ADR novo `adr-002X-split-payment.md`):
   * Receber webhook PSP × calcular CBS/IBS por transação?
   * Cliente FiscalAI escolhe PSP via marketplace ou hardcoded?
2. Migration nova para `transacao_split_payment` (referência ao
   `documento_fiscal` + `transacao_bancaria` + valor retido).
3. Novo módulo `app/modules/split_payment/`:
   * `repo.py`, `service.py`, `router.py` (webhook receiver).
4. Integração com 2-3 PSPs principais (Stripe + Pagar.me) — depende
   das APIs publicadas em 2026/2027.
5. Validação cruzada: split retido = CBS+IBS apurado do mês × % do
   pagamento. Discrepância > 5% gera alerta.
6. Atualizar `log_agente.md` + ADR.

**Dependências:** depende de #19 (Focus emitir NFS-e com CBS/IBS) +
#20 (alíquotas IBS por UF). Sem esses 2, o split payment não tem como
calcular o valor a reter.

**Marco:** Fase 5 do PlanoBackend (escopo Lucro Real). Pode ser
antecipado se Comitê Gestor publicar regulamentação em 2026.

---

## #23 — Bloco K SPED com CBS/IBS

**Trigger de ativação:** Primeiro cliente industrial aparece no
marketplace ou piloto. Hoje o Bloco K (controle de produção/estoque)
só é exigido pra indústrias com FAT > R$300M — fora do nicho PME atual.

**Trabalho técnico** (~5-7 dias — escopo Fase 5):

1. Implementar Bloco K no `gerador_icms_ipi.py`: K001/K100/K200/K220/
   K230/K235/K250/K255/K260/K265/K270/K275/K280/K290/K291/K292/K300/
   K301/K302/K990. Cada registro tem regra própria.
2. Integrar CBS/IBS por produto/item (não-agregado): cada movimento
   de estoque + transformação produtiva calcula impostos por NCM.
3. Módulo novo `app/modules/estoque/` (não existe ainda — depende de
   sprint dedicada de produto).
4. Testes: golden tests para empresa industrial canônica (fluxo MP →
   semielaborado → produto acabado).
5. Atualizar `log_agente.md`.

**Dependências:** módulo de estoque (não-existente). Bloco K não vai
entrar sem estoque primeiro.

**Marco:** Fase 5 do PlanoBackend (Lucro Real + indústria). Não
prioritário pré-piloto.

---

## #24 — NFC-e/CT-e/MDF-e com CBS/IBS

**Trigger de ativação:** RFB publica leiautes finais para documentos
não-NF-e com CBS/IBS por linha. Hoje só NF-e 4.0 + NFS-e ADN têm
campos. NFC-e (modelo 65), CT-e (modelo 57), MDF-e (modelo 58)
seguem leiautes próprios que estão sendo atualizados.

**Trabalho técnico** (~3-4 dias):

1. Atualizar parsers em `app/modules/ingestao/parsers/`:
   * `nfce_xml.py` (já existe — adicionar parse CBS/IBS por `<det>`).
   * `cte_xml.py` (criar — depende de #29 entrega).
   * `mdfe_xml.py` (criar — depende de #29 entrega).
2. `documento_fiscal_item` (Sprint 18 PR1) já suporta CBS/IBS por
   item — só falta o parser popular.
3. Atualizar geradores SPED para incluir CBS/IBS nos blocos D
   (CT-e/MDF-e) — depende de #29 também.
4. Testes: golden tests por XML real publicado pela RFB.
5. Atualizar `log_agente.md`.

**Dependências:** depende de #29 (CT-e/MDF-e bloco D — já tratada
estruturalmente na Sprint 19.8 como stub). #29 + #24 entram juntas
quando o primeiro cliente de transporte aparecer.

---

## Manutenção deste runbook

Quando um item for ativado:

1. Implementar o trabalho técnico descrito.
2. Atualizar a entrada acima: ~~strikethrough~~ + adicionar nota "✅
   Resolvida em Sprint X PRy (DATA)".
3. Mudar tag `status` no frontmatter desta nota: passar item para a
   lista "Histórico de ativações".
4. Atualizar `log_agente.md` — trocar `[externo-runbook]` por ✅.

Quando um trigger novo aparecer (ex.: RFB anuncia data oficial), abrir
PR específico atualizando este arquivo com a data alvo.

## Relacionado

- [[PlanoBackend]] §1.1 (escopo Fase 5)
- [[principios/11-out-of-scope]]
- [[principios/12-transmissao-consciente]]
- [[sprints/sprint-14-reforma]] (CBS/IBS informacional inicial)
- [[sprints/sprint-19-8-cleanup-externos]] (sprint que fechou trilha)
- `log_agente.md` §"Pendências conscientes" — buscar `[externo-runbook]`
