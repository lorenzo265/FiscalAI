"""Sprint 19.6 PR2 — Substitui S-2400 (RPPS) por S-2300 (TSVE) em evento_esocial.

Revision ID: 0048
Revises: 0047
Create Date: 2026-05-27

Pendência #14 do `log_agente.md`: Sprint 10 PR3 registrou sócios
beneficiários de pró-labore com `tipo_evento='S-2400'` — leiaute oficial
S-2400 é "Cadastro Beneficiário Ente Público / RPPS" (regime próprio de
servidores públicos). eSocial rejeitaria o evento em produção real
(tpRegPrev/categ não casam).

Substituição correta: **S-2300 — Trabalhador sem Vínculo de Emprego /
Estatutário — Início**. Evento canônico do leiaute pra registrar início
de prestação de serviços de:

  * Sócio recebendo pró-labore (categoria 723 — contribuinte individual).
  * Dirigente sindical, conselheiro, estagiário, autônomo, etc.

Esta migration:

  1. Faz **backfill** dos eventos existentes com `tipo_evento='S-2400'`
     mudando para `'S-2300'`. Como o sistema ainda não está em prod e
     todos os payloads S-2400 foram gerados pra sócio (categ 701), são
     todos elegíveis pra S-2300 conceitualmente — o payload JSONB pode
     ter formato antigo (`info_benef`), mas regenerar via service
     re-emite no formato S-2300 (`trabSemVinc`/`infoTSVInicio`).

  2. Atualiza o CHECK constraint pra aceitar apenas
     ``'S-1200','S-1210','S-2200','S-2299','S-2300'`` (sem S-2400).

**Princípios cravados:**

  * §8.2 — Eventos existentes têm `payload` JSONB inalterado nesta
    migration (preserva trilha de auditoria). Apenas `tipo_evento` é
    atualizado pra ficar coerente com novo CHECK. Re-gerar evento via
    `POST /v1/empresas/{eid}/pessoal/esocial/eventos` produz o payload
    correto no novo formato S-2300.
  * §8.6 — CHECK trocado garante que tentativas futuras de inserir
    S-2400 caem em violação de constraint (defesa em profundidade).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1) Drop CHECK constraint antigo (referencia S-2400).
    op.drop_constraint(
        "ck_esocial_tipo", "evento_esocial", type_="check"
    )

    # 2) Backfill: tipo_evento='S-2400' → 'S-2300'. Em prod ainda zerado;
    # em ambientes que rodaram a Sprint 10 PR3, todos os S-2400 são pra
    # sócio (categ 701), elegíveis pra S-2300.
    op.execute(
        sa.text(
            "UPDATE evento_esocial SET tipo_evento = 'S-2300' "
            "WHERE tipo_evento = 'S-2400'"
        )
    )

    # 3) Cria CHECK constraint novo aceitando S-2300 (sem S-2400).
    op.create_check_constraint(
        "ck_esocial_tipo",
        "evento_esocial",
        "tipo_evento IN ('S-1200','S-1210','S-2200','S-2299','S-2300')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_esocial_tipo", "evento_esocial", type_="check"
    )
    # Backfill reverso (S-2300 → S-2400) — preserva idempotência conceitual
    # do par upgrade/downgrade. Pode haver "S-2300" novos genuínos que não
    # vieram de S-2400; downgrade é destrutivo conscientemente.
    op.execute(
        sa.text(
            "UPDATE evento_esocial SET tipo_evento = 'S-2400' "
            "WHERE tipo_evento = 'S-2300'"
        )
    )
    op.create_check_constraint(
        "ck_esocial_tipo",
        "evento_esocial",
        "tipo_evento IN ('S-1200','S-1210','S-2200','S-2299','S-2400')",
    )
