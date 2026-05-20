"""Gerador puro do payload R-4020 — EFD-Reinf (Sprint 11 PR2).

Camada 1 (determinística). Função pura, zero I/O.

Espelha 1:1 a estrutura do leiaute EFD-Reinf v2.1.2 — quando o XML real for
implementado, o mapeamento dict→tag é mecânico.

Apenas R-4020 (pagamentos a beneficiários PJ) é coberto nesta sprint. Demais
eventos (R-2010 retenção previdenciária, R-9000 exclusão) virão depois.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.shared.types import JsonObject

ALGORITMO_VERSAO = "reinf.skeleton.v1"
_VERSAO_LEIAUTE = "2.1.2"


@dataclass(frozen=True, slots=True)
class BeneficiarioPjInput:
    cnpj: str
    razao_social: str


@dataclass(frozen=True, slots=True)
class ContratanteInput:
    cnpj: str
    razao_social: str


@dataclass(frozen=True, slots=True)
class RetencaoR4020Input:
    competencia: date
    valor_bruto_servico: Decimal
    ir_retido: Decimal
    pis_retido: Decimal
    cofins_retido: Decimal
    csll_retido: Decimal
    descricao: str | None = None


def gerar_r4020(
    contratante: ContratanteInput,
    beneficiario: BeneficiarioPjInput,
    retencao: RetencaoR4020Input,
) -> JsonObject:
    """R-4020 — Pagamentos/Créditos a Beneficiário Pessoa Jurídica."""
    return {
        "tipo": "R-4020",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": {
            "indRetif": 1,           # 1 = original
            "tpAmb": 2,              # 2 = produção restrita (sandbox)
            "procEmi": 1,            # 1 = aplicativo do empregador
            "verProc": ALGORITMO_VERSAO,
            "perApur": retencao.competencia.strftime("%Y-%m"),
        },
        "ide_contri": {
            "tpInsc": 1,
            "nrInsc": contratante.cnpj,
        },
        "ide_estab": {
            "tpInscEstab": 1,
            "nrInscEstab": contratante.cnpj,
        },
        "ide_benef": {
            "cnpjBenef": beneficiario.cnpj,
            "nmRazao": beneficiario.razao_social,
        },
        "ide_pgto": {
            "descPgto": retencao.descricao or "Pagamento a beneficiário PJ",
            "info_pgto": [
                {
                    "dtFG": retencao.competencia.isoformat(),
                    "vlrBaseIR": str(retencao.valor_bruto_servico),
                    "vlrIR": str(retencao.ir_retido),
                    "vlrBaseAgreg": str(retencao.valor_bruto_servico),
                    "vlrAgreg": str(
                        retencao.pis_retido
                        + retencao.cofins_retido
                        + retencao.csll_retido
                    ),
                    "vlrPIS": str(retencao.pis_retido),
                    "vlrCOFINS": str(retencao.cofins_retido),
                    "vlrCSLL": str(retencao.csll_retido),
                }
            ],
        },
        "algoritmo_versao": ALGORITMO_VERSAO,
    }
