"""Sprint 19.6 PR1 — ICMS dia_vencimento_padrao por UF.

Revision ID: 0046
Revises: 0045
Create Date: 2026-05-27

Fecha a pendência #33 do `log_agente.md`. Sprint 17 PR2 hardcoded
dia 10 do mês seguinte como vencimento E116 (registro EFD ICMS-IPI).
UFs com prazos próprios (MG dia 9, RS dia 12, SP dia 20, etc.)
recebiam E116 com data errada — cliente pagava multa de mora se
confiasse no campo.

Estende a SCD ``aliquota_icms_uf`` com coluna ``dia_vencimento_padrao``
e seed dos 27 UFs com dias típicos para **regime normal** (não-Simples
Nacional). Empresas SN têm vencimento unificado no DAS (dia 20 do mês
seguinte) — esta tabela não serve para SN.

**Importante (out-of-scope explícito):** vencimento real de ICMS depende
muitas vezes de **CNAE** + **regime** + **porte** específicos:
  * SP: dia 20 mensal para varejo CNAE 47.x; dia 10 para indústria.
  * MG: dia 9 para indústria/comércio; dia 25 para varejo CNAE 47.71-7.
  * CE: dia 20 para varejo CNAE 47.x; dia 10 para indústria.

Para o MVP cobrimos o **vencimento principal por UF**. Casos
específicos por CNAE entram em sprint dedicada quando primeiro
cliente reclamar (pendência scope-cut futura — registrada).

**Backward-compat:** ADD COLUMN com ``server_default=10`` preserva
comportamento atual em runtime durante o deploy 2-fases (linhas
antigas mantêm valor 10 padrão). UPDATE específico por UF roda em
seguida pra atualizar para os valores corretos.

**Fontes consultadas:**
  * Convênio ICMS 92/2006 — padrão 10.
  * RICMS por UF — Resoluções SEFAZ estaduais 2020-2025.
  * SP: art. 112 RICMS-SP (Decreto 45.490/2000) — dia 20 regime mensal.
  * MG: Resolução SF 4.855/2015 — dia 9 indústria/comércio.
  * RS: art. 39 RICMS-RS (Decreto 37.699/1997) — dia 12 mensal.
  * BA: art. 332 RICMS-BA (Decreto 13.780/2012) — dia 9.

**Princípio cravado:** §8.3 — SCD Type 2. Quando UF mudar o dia (raro,
mas acontece), insere-se nova linha via painel admin (Sprint 19.5
PR1) sem alterar histórico.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | None = None
depends_on: str | None = None


# Dias típicos de vencimento ICMS por UF — regime normal mensal.
# Não cobre SN (DAS unificado dia 20) nem CNAEs específicos que
# têm regras próprias dentro da mesma UF. Default 10 cobre os
# casos não-listados (Convênio ICMS 92/2006).
_DIA_VENCIMENTO_POR_UF: dict[str, int] = {
    "AC": 15,   # Decreto estadual AC
    "AL": 10,   # RICMS-AL
    "AM": 10,   # Resolução GSEFAZ AM
    "AP": 10,   # RICMS-AP
    "BA": 9,    # RICMS-BA art. 332
    "CE": 10,   # RICMS-CE (varejo dia 20 — out-of-scope CNAE)
    "DF": 14,   # RICMS-DF
    "ES": 6,    # RICMS-ES (dia 6 — bem antecipado)
    "GO": 10,   # RICMS-GO
    "MA": 20,   # DOE-MA 2010 — dia 20 geral
    "MG": 9,    # Resolução SF 4.855/2015 — indústria/comércio
    "MS": 11,   # RICMS-MS
    "MT": 6,    # RICMS-MT
    "PA": 10,   # RICMS-PA
    "PB": 15,   # RICMS-PB
    "PE": 15,   # RICMS-PE
    "PI": 15,   # RICMS-PI
    "PR": 12,   # CRC-PR
    "RJ": 10,   # RICMS-RJ (varejo varia por CNAE)
    "RN": 10,   # RICMS-RN
    "RO": 11,   # RICMS-RO
    "RR": 10,   # RICMS-RR
    "RS": 12,   # RICMS-RS art. 39
    "SC": 10,   # RICMS-SC
    "SE": 10,   # RICMS-SE
    "SP": 20,   # RICMS-SP art. 112 — regime mensal padrão
    "TO": 5,    # RICMS-TO — bem antecipado
}


def upgrade() -> None:
    # 1) ADD COLUMN com default 10 — backward-compat (linhas existentes
    # ganham valor 10 que mantém comportamento atual no service).
    op.add_column(
        "aliquota_icms_uf",
        sa.Column(
            "dia_vencimento_padrao",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    # CHECK 1..28 pra garantir dia válido em qualquer mês (fevereiro
    # tem 28 — usar dia 29-31 quebraria em fevereiro). Dia 20 já é
    # antecipado pra maioria dos casos do mundo real.
    op.create_check_constraint(
        "ck_icms_dia_vencimento_padrao",
        "aliquota_icms_uf",
        "dia_vencimento_padrao BETWEEN 1 AND 28",
    )

    # 2) UPDATE seed — propaga dias específicos por UF nas linhas
    # ativas (valid_to IS NULL = vigência corrente). Linhas históricas
    # mantêm o default 10 — não vale a pena recalcular vencimento de
    # apurações antigas (SPED já foi gerado/transmitido).
    for uf, dia in _DIA_VENCIMENTO_POR_UF.items():
        op.execute(
            sa.text(
                "UPDATE aliquota_icms_uf SET dia_vencimento_padrao = :dia "
                "WHERE uf = :uf AND valid_to IS NULL"
            ).bindparams(uf=uf, dia=dia)
        )


def downgrade() -> None:
    op.drop_constraint(
        "ck_icms_dia_vencimento_padrao", "aliquota_icms_uf", type_="check"
    )
    op.drop_column("aliquota_icms_uf", "dia_vencimento_padrao")
