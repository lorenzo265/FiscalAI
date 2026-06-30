"""DTOs do contrato DistribuiçãoDFe (NFeDistribuicaoDFe) — MD-e PR2.

Fonte: NT 2014.002 v1.20 / retDistDFeInt (SEFAZ Ambiente Nacional).

Layout do response:
  * ``retDistDFeInt.ultNSU`` — último NSU processado nesta consulta.
  * ``retDistDFeInt.maxNSU`` — maior NSU existente no AN para o CNPJ.
  * Cada documento chega como ``docZip`` comprimido em gzip:
      - schema ``resNFe_v1.01.xsd``   → resumo antes da Ciência.
      - schema ``nfeProc_v4.00.xsd``  → XML completo após Ciência (210210).
      - schema ``procEventoNFe_v1.00.xsd`` → evento de interesse (pós v1.20).

Quando ``ultNSU == maxNSU``, não há mais documentos a consumir no momento.
O loop de sincronização para neste caso.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

# Tipo de documento distribuído pelo DistribuiçãoDFe.
# 'resumo'   → resNFe    (antes da Ciência — somente dados sumários)
# 'completo' → nfeProc   (após Ciência registrada — XML completo)
TipoDocumentoMde = Literal["resumo", "completo"]


@dataclass(frozen=True, slots=True)
class ResumoNFeDestinada:
    """DTO de um documento retornado pelo DistribuiçãoDFe.

    Campos presentes tanto no resumo (resNFe) quanto no completo (nfeProc).
    ``xml_completo`` é não-None apenas quando ``tipo_documento == 'completo'``.
    Dinheiro em Decimal (nunca float).
    """

    chave_nfe: str  # 44 dígitos
    nsu: int  # NSU deste documento no Ambiente Nacional
    emitente_cnpj: str | None
    emitente_nome: str | None
    valor_total: Decimal | None  # vNF — NUMERIC, nunca float
    dh_emissao: datetime | None  # aware (UTC ou BR)
    tipo_documento: TipoDocumentoMde
    xml_completo: str | None  # XML bruto (apenas quando tipo_documento='completo')


@dataclass(frozen=True, slots=True)
class ResultadoDistribuicao:
    """Resultado de uma chamada a ``baixar_documentos``.

    ``ult_nsu`` avança a cada chamada e deve ser persistido no cursor.
    Quando ``ult_nsu >= max_nsu``, o loop de sincronização deve parar
    (não há mais documentos no momento).
    """

    documentos: list[ResumoNFeDestinada] = field(default_factory=list)
    ult_nsu: int = 0  # último NSU retornado nesta consulta
    max_nsu: int = 0  # maior NSU disponível no AN para o CNPJ
