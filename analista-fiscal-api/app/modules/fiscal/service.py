from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.fiscal.calcula_das import FaixaDAS, ResultadoDAS, calcular_das, resolver_anexo_fator_r
from app.modules.fiscal.repo import ApuracaoFiscalRepo, TabelaSimplesRepo
from app.modules.fiscal.schemas import ApuracaoDASIn
from app.shared.db.models import ApuracaoFiscal
from app.shared.exceptions import (
    ApuracaoJaExiste,
    ApuracaoNaoEncontrada,
    EmpresaNaoEncontrada,
    FatorRObrigatorio,
    RegimeIncompativel,
    TabelaTributariaAusente,
)

log = structlog.get_logger(__name__)

_REGIME_SN = "simples_nacional"
_TIPO_DAS = "das"


def _competencia_para_date(competencia_str: str) -> date:
    """Converte "YYYY-MM" para o primeiro dia do mês."""
    ano, mes = competencia_str.split("-")
    return date(int(ano), int(mes), 1)


def _modelo_para_faixa(m: object) -> FaixaDAS:
    from app.shared.db.models import TabelaSimplesFaixa

    assert isinstance(m, TabelaSimplesFaixa)
    return FaixaDAS(
        faixa=m.faixa,
        rbt12_ate=m.rbt12_ate,
        aliquota_nominal=m.aliquota_nominal,
        parcela_deduzir=m.parcela_deduzir,
    )


class FiscalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._empresa_repo = EmpresaRepo(session)
        self._tabela_repo = TabelaSimplesRepo(session)
        self._apuracao_repo = ApuracaoFiscalRepo(session)

    async def calcular_e_salvar_das(
        self,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApuracaoDASIn,
    ) -> ApuracaoFiscal:
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if empresa.regime_tributario != _REGIME_SN:
            raise RegimeIncompativel(
                f"DAS é exclusivo do Simples Nacional; "
                f"empresa tem regime '{empresa.regime_tributario}'"
            )

        anexo = empresa.anexo_simples or "I"
        competencia_date = _competencia_para_date(payload.competencia)

        existente = await self._apuracao_repo.buscar(empresa_id, competencia_date, _TIPO_DAS)
        if existente is not None:
            raise ApuracaoJaExiste(
                f"DAS de {payload.competencia} já calculado para empresa {empresa_id}; "
                "use PATCH para atualizar"
            )

        if payload.rbt12_override is not None:
            rbt12 = payload.rbt12_override
        else:
            # Fase 2 PR3: RBT12 derivado de rbt12_mensal (view materializada).
            # Fallback para empresa.faturamento_12m (declarado no onboarding)
            # quando ainda não há documentos fiscais ingeridos para a empresa.
            rbt12_da_view = await self._empresa_repo.rbt12_da_view(
                empresa_id, competencia_date
            )
            rbt12 = (
                rbt12_da_view
                if rbt12_da_view is not None
                else (empresa.faturamento_12m or Decimal("0"))
            )

        fator_r: Decimal | None = None
        anexo_efetivo = anexo

        if anexo in ("III", "V"):
            if payload.folha_12m is None:
                raise FatorRObrigatorio(
                    f"Empresa no Anexo {anexo} — forneça folha_12m para calcular Fator R"
                )
            # Massa salarial = remuneração bruta + encargos patronais (CPP + FGTS + 13º).
            # Fonte: LC 123/2006 art. 18 §5º-J e §24; Res. CGSN 140/2018 art. 26 §1º.
            # encargos_folha_12m tem default=0 para retrocompatibilidade com callers
            # que ainda não fornecem os encargos — o Fator R será subestimado nesses casos.
            massa_salarial_12m = payload.folha_12m + payload.encargos_folha_12m
            fator_r = massa_salarial_12m / rbt12 if rbt12 > Decimal("0") else Decimal("0")
            anexo_efetivo = resolver_anexo_fator_r(anexo, fator_r)

        faixas_db = await self._tabela_repo.faixas_vigentes(anexo_efetivo, competencia_date)
        if not faixas_db:
            raise TabelaTributariaAusente(
                f"Tabela Simples Nacional Anexo {anexo_efetivo} não encontrada "
                f"para competência {payload.competencia}"
            )

        faixas = [_modelo_para_faixa(f) for f in faixas_db]

        resultado: ResultadoDAS = calcular_das(
            rbt12=rbt12,
            receita_mes=payload.receita_mes,
            faixas=faixas,
            anexo=anexo,
            anexo_efetivo=anexo_efetivo,
            fator_r=fator_r,
            uf=empresa.uf,
            sublimite_estadual=payload.sublimite_estadual,
        )

        faixas_dict = [
            {
                "faixa": f.faixa,
                "rbt12_ate": str(f.rbt12_ate),
                "aliquota_nominal": str(f.aliquota_nominal),
                "parcela_deduzir": str(f.parcela_deduzir),
            }
            for f in faixas
        ]

        apuracao = ApuracaoFiscal(
            id=uuid4(),
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=competencia_date,
            tipo=_TIPO_DAS,
            regime=_REGIME_SN,
            input_jsonb={
                "rbt12": str(rbt12),
                "receita_mes": str(payload.receita_mes),
                "folha_12m": str(payload.folha_12m) if payload.folha_12m is not None else None,
                "encargos_folha_12m": str(payload.encargos_folha_12m),
                # massa_salarial_12m = folha_12m + encargos_folha_12m (Fator R real)
                "massa_salarial_12m": (
                    str(payload.folha_12m + payload.encargos_folha_12m)
                    if payload.folha_12m is not None
                    else None
                ),
                "competencia": payload.competencia,
            },
            output_jsonb={
                "anexo": resultado.anexo,
                "anexo_efetivo": resultado.anexo_efetivo,
                "faixa": resultado.faixa,
                "rbt12_usado": str(resultado.rbt12_usado),
                "aliquota_nominal": str(resultado.aliquota_nominal),
                "aliquota_efetiva": str(resultado.aliquota_efetiva),
                "receita_mes": str(resultado.receita_mes),
                "valor_das": str(resultado.valor),
                "fator_r": str(resultado.fator_r) if resultado.fator_r is not None else None,
                "algoritmo_versao": resultado.algoritmo_versao,
                "uf": resultado.uf,
                "sublimite_aplicado": str(resultado.sublimite_aplicado),
                "sublimite_excedido": resultado.sublimite_excedido,
                "receitas_por_anexo": {
                    a: str(v) for a, v in resultado.receitas_por_anexo.items()
                },
            },
            faixas_usadas={"faixas": faixas_dict, "anexo_efetivo": anexo_efetivo},
            algoritmo_versao=resultado.algoritmo_versao,
            status="calculado",
        )

        salva = await self._apuracao_repo.salvar(apuracao)
        await self._session.commit()

        log.info(
            "fiscal.das.calculou",
            empresa_id=str(empresa_id),
            competencia=payload.competencia,
            anexo=anexo,
            anexo_efetivo=anexo_efetivo,
            faixa=resultado.faixa,
            valor_das=str(resultado.valor),
            algoritmo_versao=resultado.algoritmo_versao,
        )

        return salva

    async def buscar_das(
        self, empresa_id: UUID, competencia_str: str
    ) -> ApuracaoFiscal:
        competencia_date = _competencia_para_date(competencia_str)
        apuracao = await self._apuracao_repo.buscar(empresa_id, competencia_date, _TIPO_DAS)
        if apuracao is None:
            raise ApuracaoNaoEncontrada(
                f"DAS de {competencia_str} não encontrado para empresa {empresa_id}"
            )
        return apuracao
