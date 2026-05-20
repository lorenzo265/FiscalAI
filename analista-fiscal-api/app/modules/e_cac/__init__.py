"""Módulo de monitoramento e-CAC (Sprint 6 PR2).

Sincroniza a caixa postal RFB do contribuinte via SERPRO Integra Contador
(idServico ``MSGCONTRIBUINTE51``), persiste novas mensagens em
``mensagem_e_cac`` (UNIQUE por id_externo_serpro → idempotente) e classifica
por palavra-chave (LLM no PR3).
"""
