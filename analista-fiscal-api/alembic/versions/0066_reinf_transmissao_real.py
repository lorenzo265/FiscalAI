"""Marco 4 PR2 -- EFD-Reinf transmissao real (pendencia #11 do PLANO_GO_LIVE).

Revision ID: 0066
Revises: 0065
Create Date: 2026-06-23

Espelha a 0051 (eSocial transmissao real) para o `efd_reinf_evento`. A
Sprint 11 PR2 entregou apenas o payload JSONB do R-4020 (status='preparado'
permanente); o envio real (assinatura XMLDSig -> envio API SERPRO/RFB ->
recibo -> status final) era a pendencia #11 do go-live.

**Mudancas (todas backward-compatible -- colunas novas nullable):**

  * `processado_em` TIMESTAMPTZ -- quando o recibo final foi aplicado.
  * `xml_assinado` BYTEA -- XML do evento apos XMLDSig (~5KB). Mesmo
    racional do eSocial: eventos sao pequenos, BYTEA aceitavel ate o
    storage S3 (Marco 4 #10) cobrir tambem estes blobs.
  * `lote_protocolo` VARCHAR(40) -- protocolo do lote recebido no POST de
    recepcao; varios eventos compartilham o mesmo lote.
  * `recibo_numero` VARCHAR(40) -- numero do recibo final por evento.
  * `hash_xml` VARCHAR(64) -- SHA256 hex do XML canonico pre-assinatura
    (idempotencia forte).
  * Indice `ix_reinf_lote_protocolo` para o poll "todos os eventos do lote X".

`efd_reinf_evento` NAO tem CHECK em status/tipo_evento (diferente do
eSocial) -- nada a alterar em constraint. Tabela ja existe (Sprint 11 PR2,
migration 0020) com RLS + grants; nenhum GRANT novo necessario.

**Principios cravados:**

  * Sec. 8.2 -- XML assinado e fato imutavel; status final atualiza apenas
    campos operacionais (`transmitido_em`, `processado_em`, `recibo_numero`,
    `resposta`). Cancelamento real vira evento R-9000 separado.
  * Sec. 8.9 -- `lote_protocolo` e idempotency key natural; UNIQUE
    `uq_reinf_empresa_tipo_ref` (Sprint 11 PR2) garante 1 evento por ref.
  * Sec. 8.12 -- transmissao e ato consciente; flag REINF_TRANSMISSAO_ATIVA
    default False (config.py). A migration so habilita o schema.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0066"
down_revision: str | None = "0065"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "efd_reinf_evento",
        sa.Column("processado_em", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "efd_reinf_evento",
        sa.Column("xml_assinado", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "efd_reinf_evento",
        sa.Column("lote_protocolo", sa.String(40), nullable=True),
    )
    op.add_column(
        "efd_reinf_evento",
        sa.Column("recibo_numero", sa.String(40), nullable=True),
    )
    op.add_column(
        "efd_reinf_evento",
        sa.Column("hash_xml", sa.String(64), nullable=True),
    )

    op.create_index(
        "ix_reinf_lote_protocolo",
        "efd_reinf_evento",
        ["lote_protocolo"],
        postgresql_where=sa.text("lote_protocolo IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_reinf_lote_protocolo", table_name="efd_reinf_evento")
    op.drop_column("efd_reinf_evento", "hash_xml")
    op.drop_column("efd_reinf_evento", "recibo_numero")
    op.drop_column("efd_reinf_evento", "lote_protocolo")
    op.drop_column("efd_reinf_evento", "xml_assinado")
    op.drop_column("efd_reinf_evento", "processado_em")
