"""Marketplace de contadores parceiros — Sprint 13.

Bounded context responsável por:

  * Cadastro e curadoria de ``ContadorParceiro`` (pool global, §5.8).
  * Catálogo de categorias com pricing + SLA (§10.3).
  * Conjunto fechado de especialidades + mapping categoria → especialidade.

PR1 entrega o schema, o cadastro e a curadoria. Fluxo de consulta (criar /
aceitar / responder / avaliar), integração com o assistente e auth do parceiro
ficam no PR2 e PR3.
"""
