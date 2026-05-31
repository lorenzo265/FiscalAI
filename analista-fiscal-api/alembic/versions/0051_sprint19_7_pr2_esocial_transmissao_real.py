"""Sprint 19.7 PR2 — eSocial transmissão real (pendência #13).

Revision ID: 0051
Revises: 0050
Create Date: 2026-05-29

Esta migration prepara `evento_esocial` para o ciclo completo de
transmissão (assinatura XMLDSig → envio API eSocial → recibo → status
final). Sprint 10 PR3 + Sprint 19.6 PR2 entregaram apenas geração de
payload + XML canônico; envio real era pendência consciente #13.

**Mudanças:**

  1. **CHECK constraint** atualizado para aceitar **5 novos eventos** do
     leiaute S-1.3 que não estavam cobertos:

       * **S-2205** — Alteração de Dados Cadastrais do Trabalhador.
       * **S-2206** — Alteração de Contrato de Trabalho.
       * **S-2230** — Afastamento Temporário (licença, atestado, etc.).
       * **S-2298** — Reintegração (anulação de S-2299 anterior).
       * **S-3000** — Exclusão de Evento (cancela qualquer evento
         transmitido anteriormente, por chave + Id).

     Mantém os 5 já aceitos: S-1200, S-1210, S-2200, S-2299, S-2300.

  2. **Status** ganha novos valores no CHECK:

       * **'assinado'** — XMLDSig aplicado; pronto pra enviar.
       * **'em_lote'** — agrupado num lote enviado; aguardando recibo.
       * **'rejeitado_xsd'** — falhou validação XSD local antes do envio.

     Mantém: 'preparado', 'transmitido', 'aceito', 'rejeitado',
     'cancelado'.

  3. **Colunas novas:**

       * **`xml_assinado` BYTEA** — XML após XMLDSig (~5KB cada).
         Armazenado por enquanto direto em BYTEA — pendência #2
         (S3/GCS) ainda não resolvida. ECD/ECF maiores já usam
         `arquivo_sped.conteudo_bytea`; eventos eSocial são
         orders-of-magnitude menores (5–20KB), aceitável.
       * **`lote_protocolo` VARCHAR(40)** — protocolo do lote eSocial
         recebido no POST `/lotes/eventos`. Vários eventos compartilham
         o mesmo `lote_protocolo` (máx 50 por lote — limite oficial).
       * **`recibo_numero` VARCHAR(40)** — número do recibo final
         retornado em `GET /lotes/eventos/{protocolo}` quando o
         processamento termina (estado=4).
       * **`hash_xml` VARCHAR(64)** — SHA256 hex do XML canônico
         pré-assinatura. Usado pra detectar regeneração do mesmo
         payload (idempotência forte).

  4. **Índice** novo `ix_esocial_lote_protocolo` para consultas
     "todos os eventos do lote X" (poll de recibo).

**Princípios cravados:**

  * §8.2 — XML assinado é fato imutável; status final substitui linha
    via `UPDATE` apenas em campos operacionais (`transmitido_em`,
    `processado_em`, `recibo_numero`, `resposta`). Cancelamento real
    vira evento S-3000 separado (não mexe na linha original).
  * §8.9 — `lote_protocolo` é idempotency key natural; mesmo lote
    enviado 2× recupera o protocolo existente. UNIQUE
    `uq_esocial_empresa_tipo_ref` (Sprint 10 PR3) garante 1 evento por
    referência.
  * §8.12 — Transmissão é ato consciente — flag
    `ESOCIAL_TRANSMISSAO_ATIVA=false` por default (config.py); migration
    apenas habilita o schema, mas o service só envia se admin opt-in.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | None = None
depends_on: str | None = None


_TIPOS_NOVOS = (
    "'S-1200','S-1210','S-2200','S-2205','S-2206','S-2230','S-2298',"
    "'S-2299','S-2300','S-3000'"
)
_TIPOS_ANTIGOS = "'S-1200','S-1210','S-2200','S-2299','S-2300'"
_STATUS_NOVOS = (
    "'preparado','assinado','em_lote','transmitido','aceito',"
    "'rejeitado','rejeitado_xsd','cancelado'"
)
_STATUS_ANTIGOS = (
    "'preparado','transmitido','aceito','rejeitado','cancelado'"
)


def upgrade() -> None:
    # 1) CHECK tipo_evento — adiciona S-2205/2206/2230/2298/3000.
    op.drop_constraint("ck_esocial_tipo", "evento_esocial", type_="check")
    op.create_check_constraint(
        "ck_esocial_tipo",
        "evento_esocial",
        f"tipo_evento IN ({_TIPOS_NOVOS})",
    )

    # 2) CHECK status — adiciona 'assinado', 'em_lote', 'rejeitado_xsd'.
    op.drop_constraint("ck_esocial_status", "evento_esocial", type_="check")
    op.create_check_constraint(
        "ck_esocial_status",
        "evento_esocial",
        f"status IN ({_STATUS_NOVOS})",
    )

    # 3) Colunas novas — todas nullable (backfill nesse mesmo deploy +
    # NOT NULL eventualmente é overkill: campos opcionais por design).
    op.add_column(
        "evento_esocial",
        sa.Column("xml_assinado", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "evento_esocial",
        sa.Column("lote_protocolo", sa.String(40), nullable=True),
    )
    op.add_column(
        "evento_esocial",
        sa.Column("recibo_numero", sa.String(40), nullable=True),
    )
    op.add_column(
        "evento_esocial",
        sa.Column("hash_xml", sa.String(64), nullable=True),
    )

    # 4) Índice pra poll de recibo por lote.
    op.create_index(
        "ix_esocial_lote_protocolo",
        "evento_esocial",
        ["lote_protocolo"],
        postgresql_where=sa.text("lote_protocolo IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_esocial_lote_protocolo", table_name="evento_esocial")
    op.drop_column("evento_esocial", "hash_xml")
    op.drop_column("evento_esocial", "recibo_numero")
    op.drop_column("evento_esocial", "lote_protocolo")
    op.drop_column("evento_esocial", "xml_assinado")

    op.drop_constraint("ck_esocial_status", "evento_esocial", type_="check")
    op.create_check_constraint(
        "ck_esocial_status",
        "evento_esocial",
        f"status IN ({_STATUS_ANTIGOS})",
    )

    # Backfill antes de apertar CHECK — apaga eventos com tipos novos
    # (downgrade é destrutivo conscientemente, igual 0048).
    op.execute(
        sa.text(
            "DELETE FROM evento_esocial "
            "WHERE tipo_evento IN ('S-2205','S-2206','S-2230','S-2298','S-3000')"
        )
    )
    op.drop_constraint("ck_esocial_tipo", "evento_esocial", type_="check")
    op.create_check_constraint(
        "ck_esocial_tipo",
        "evento_esocial",
        f"tipo_evento IN ({_TIPOS_ANTIGOS})",
    )
