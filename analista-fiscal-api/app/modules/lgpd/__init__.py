"""Bounded context LGPD -- direito do titular (Marco 3, LGPD art. 18).

Endpoints de portabilidade (``/v1/lgpd/exportar``) e, na sequencia, de
esquecimento por anonimizacao (``/v1/lgpd/excluir``), com trilha de auditoria
em ``lgpd_solicitacao``. Respeita a imutabilidade fiscal (principio 8.2) e a
retencao legal de 5 anos: a exclusao ANONIMIZA a PII, nao apaga o fato fiscal.
"""
