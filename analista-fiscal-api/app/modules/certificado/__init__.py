"""Cofre de certificado A1 (.p12 ICP-Brasil) por empresa.

Bounded context: o cliente sobe o seu certificado e-CNPJ A1 (arquivo .p12 +
senha); o sistema **valida**, extrai os metadados (CN, CNPJ, validade,
fingerprint) e guarda o material **cifrado em repouso** (envelope AES-256-GCM,
§8.7). O cert é o que destrava a assinatura XMLDSig das transmissões reais
(eSocial, EFD-Reinf, MD-e) — todas passam pelo único ponto de entrada
``app.shared.crypto.cert_loader.carregar_cert_a1``.

Custódia da senha (decisão do PO 2026-06-30): guardada cifrada para permitir
transmissão automática/agendada. Decifrada só no ato do envio; nunca em log.
"""
