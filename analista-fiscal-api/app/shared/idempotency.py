"""Namespaces UUID5 para idempotência §8.9.

Cada caminho que constrói uma ``idempotency_key`` via ``uuid.uuid5`` deve
referenciar **um** namespace dedicado declarado aqui. Trocar o valor de um
namespace é **breaking change** — re-POSTs antigos passariam a parecer
chamadas novas e duplicariam efeitos colaterais.

Convenção do projeto até a Sprint 19.5:

  * Integrações externas (SERPRO / Focus / Pluggy) usam ``idempotency_key``
    em formato STRING (composta no service, ex.: ``apuracao:<empresa>:<comp>``).
    Não convertem para UUID5 — string-based é suficiente porque o lado
    upstream também é string.

  * **Painel admin de tabelas tributárias (Sprint 19.5)** introduz o primeiro
    namespace UUID5 do projeto. A chave é estruturada
    (``{tipo}|{valid_from}|{sha256(payload_canonico)}``) e precisa caber no
    UNIQUE da coluna ``vigencia_tabela_log.idempotency_key UUID NOT NULL``.

UUIDs dos namespaces são fixos — gerados via ``uuid4()`` uma única vez e
cravados no código. Não regenerar: já existem dados no DB com hashes
derivados destes valores.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

# Namespace UUID5 para idempotência do painel admin (Sprint 19.5 PR1+).
# Cobre os 3 PRs:
#   PR1 — POST /v1/admin/tabelas/<tipo>/vigencia (criação de vigência tributária)
#   PR2 — worker tabelas.verificar_vigencias (1 alerta por tipo+ano)
#   PR3 — worker tabelas.varrer_dou_mensal (1 sugestão por URL DOU)
#
# Gerado uma única vez via uuid4() — NÃO REGENERAR. Mudar este valor invalida
# todos os logs existentes em ``vigencia_tabela_log``, todos os alertas em
# ``alerta_admin`` e todas as sugestões em ``sugestao_vigencia_tabela`` que
# foram persistidos com a chave derivada dele.
NS_TABELA_ADMIN: Final[UUID] = UUID("3f1c5d3e-7a4b-4d2c-8e9f-0a1b2c3d4e5f")


__all__ = ["NS_TABELA_ADMIN"]
