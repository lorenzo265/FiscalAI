from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.multa_juros.calcula_selic import ALGORITMO_VERSAO


class SimularMoraIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valor: Decimal = Field(gt=Decimal("0"), description="Valor principal do tributo (R$)")
    data_vencimento: date
    data_pagamento: date

    @model_validator(mode="after")
    def pagamento_nao_anterior_a_vencimento(self) -> SimularMoraIn:
        if self.data_pagamento < self.data_vencimento:
            raise ValueError("data_pagamento não pode ser anterior a data_vencimento")
        return self


class SimularMoraOut(BaseModel):
    valor_original: Decimal
    multa_mora: Decimal
    juros_selic: Decimal
    acrescimo_mes_pagamento: Decimal
    total_acrescimos: Decimal
    valor_atualizado: Decimal
    dias_atraso: int
    meses_selic: int
    aliquota_multa: Decimal
    aliquota_juros_acumulada: Decimal
    data_vencimento: date
    data_pagamento: date
    algoritmo_versao: str = ALGORITMO_VERSAO
