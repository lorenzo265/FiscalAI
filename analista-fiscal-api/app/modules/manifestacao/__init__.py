"""Manifestação do Destinatário de NF-e (MD-e) — bounded context.

Obrigação legal do destinatário (tomador) de NF-e: registrar eventos sobre
notas emitidas contra seu CNPJ no Ambiente Nacional SEFAZ (cOrgao=91).

4 eventos (NT 2014.002 / NT 2020.001):
  210200 — Confirmação da Operação
  210210 — Ciência da Operação
  210220 — Desconhecimento da Operação
  210240 — Operação não Realizada  (exige justificativa 15–255 chars)

Camadas deste módulo:
  manifestacao_xml.py — geração XML pura (determinística, golden-testável).
  repo.py             — acesso ao banco (async, selectinload onde houver join).
  service.py          — orquestra: valida → gera XML → assina → persiste.
  schemas.py          — contratos Pydantic v2 (inputs com extra=forbid).
  router.py           — thin: valida → service → response_model.

PR1 entrega: persistência + assinatura (NotImplemented em dev/CI).
PR2: ligação com client SEFAZ real.
PR3: transmissão + polling de recibo.

§8.12 — transmissão é ato consciente do operador.
§8.1  — RLS multi-tenant via migration 0067.
§8.2  — append-only: cancelamento = novo evento no SEFAZ (não UPDATE aqui).
§8.9  — idempotência por (empresa, chave_nfe, tipo_evento, sequencial) +
        idempotency_key opaca opcional.
"""
