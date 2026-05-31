---
tags: [pendencia, reforma-tributaria, nfse, focus-nfe, sprint-14]
fonte: "Sprint 14 PR2 — flag FOCUS_NFSE_ENVIA_CBS_IBS"
status: aberta
prioridade: baixa
---

# Pendência — Emissão NFS-e com CBS/IBS via Focus NFe

> Pendência consciente da Sprint 14 PR2. Fonte: `log_agente.md` + `app/config.py::FOCUS_NFSE_ENVIA_CBS_IBS`.

A flag de configuração `FOCUS_NFSE_ENVIA_CBS_IBS` foi criada (default `False`) para gate da injeção de campos CBS/IBS/cClassTrib no payload NFS-e enviado à Focus NFe. **A Focus ainda não documenta a API com esses campos para todos os municípios brasileiros** — só 7 prefeituras-piloto têm o campo ativo no schema do padrão nacional (ADN). Mais 5.563 municípios ainda usam schemas municipais legados sem CBS/IBS.

## Ativação real

Critérios para virar a flag para `True`:

1. Focus libera documentação oficial da API com CBS/IBS para municípios do padrão nacional (ADN).
2. Comitê Gestor IBS publica regulamentação final das alíquotas por município (PLP 68/2024 sancionado).
3. Pelo menos 80% dos municípios atendidos pelos primeiros 50 pagantes têm cobertura no ADN.

## Implementação esperada

Quando ativarmos:

1. Estender `_construir_payload_focus` em `app/modules/notas/service.py` para receber a flag via Settings e injetar `cbs: {valor}`, `ibs: {valor}`, `cClassTrib: {6 dígitos}` no payload.
2. Adicionar lookup via `AliquotaCbsIbsRepo.vigente(emissao, regime, cnae, classificacao)` no service para resolver alíquotas.
3. Sanity check: o `cClassTrib` deve vir do cadastro de produto/serviço (Sprint futura — cadastro de itens com classificação LC 214 art. 9º).

## Relacionado

- [[modulos/reforma|módulo reforma]]
- [[decisoes/adr-0016-reforma-tributaria-informacional-2026|ADR 0016]]
- [[sprints/sprint-14-reforma|Sprint 14]]
