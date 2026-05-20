"""Service de eventos pontuais de folha — 13º, férias, rescisão (Sprint 10 PR2).

Cobre:
  * ``registrar_13o``        — 1ª ou 2ª parcela do 13º (idempotente por ano).
  * ``registrar_ferias``     — gozadas + abono opcional (idempotente por período).
  * ``registrar_rescisao``   — 5 modalidades CLT (idempotente por funcionário).

Em rescisão, além de criar o evento, marca o funcionário como demitido
(``data_demissao`` + ``ativo=false``) — efeito colateral consciente.

§8.2 Cada evento é fato imutável após persistido (UPDATE bloqueado por
       UNIQUE parcial — ver migration 0017).
§8.3 Snapshot completo das alíquotas vigentes vai em ``detalhes`` JSONB.
§8.9 Idempotência via UNIQUE parcial:
        13º    → (funcionario, tipo, ano_referencia)
        férias → (funcionario, tipo, periodo_inicio)
        rescisão → (funcionario, tipo)
§8.10 Log estruturado por evento.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.pessoal.calcula_13o import (
    Resultado13oPrimeira,
    Resultado13oSegunda,
    calcular_13o_primeira,
    calcular_13o_segunda,
)
from app.modules.pessoal.calcula_inss import FaixaInss
from app.modules.pessoal.calcula_irrf import FaixaIrrf
from app.modules.pessoal.calcula_ferias import (
    ResultadoFerias,
    calcular_ferias,
)
from app.modules.pessoal.calcula_rescisao import (
    RescisaoTipo,
    ResultadoRescisao,
    calcular_rescisao,
)
from app.modules.pessoal.repo import (
    EventoFolhaRepo,
    FuncionarioRepo,
    TabelasTributariasRepo,
)
from app.modules.pessoal.schemas import (
    DecimoTerceiroIn,
    FeriasIn,
    RescisaoIn,
)
from app.shared.db.models import Empresa, EventoFolha, Funcionario
from app.shared.types import JsonObject
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    EventoFolhaJaExiste,
    FuncionarioJaDemitido,
    FuncionarioNaoEncontrado,
    ParametrosFolhaInvalidos,
    TabelaTributariaAusente,
)

log = structlog.get_logger(__name__)

_ZERO = Decimal("0.00")
_DOIS = Decimal("2")


class EventosFolhaService:
    # ── Helpers comuns ──────────────────────────────────────────────────

    async def _carregar_empresa_e_func(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        funcionario_id: UUID,
    ) -> tuple[Empresa, Funcionario]:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        func = await FuncionarioRepo(session).por_id(funcionario_id)
        if func is None or func.empresa_id != empresa_id:
            raise FuncionarioNaoEncontrado(
                f"Funcionário {funcionario_id} não encontrado nesta empresa"
            )
        return empresa, func

    async def _tabelas_inss_irrf(
        self,
        session: AsyncSession,
        em: date,
    ) -> tuple[list[FaixaInss], list[FaixaIrrf]]:
        tabelas = TabelasTributariasRepo(session)
        faixas_inss = await tabelas.inss_faixas_vigentes(em, tipo="empregado")
        if len(faixas_inss) != 4:
            raise TabelaTributariaAusente(
                f"Tabela INSS empregado incompleta em {em.isoformat()} "
                f"({len(faixas_inss)} faixas; esperadas 4)"
            )
        faixas_irrf = await tabelas.irrf_faixas_vigentes(em)
        if len(faixas_irrf) != 5:
            raise TabelaTributariaAusente(
                f"Tabela IRRF incompleta em {em.isoformat()} "
                f"({len(faixas_irrf)} faixas; esperadas 5)"
            )
        return faixas_inss, faixas_irrf

    async def _commit_evento(
        self, session: AsyncSession, evento: EventoFolha
    ) -> EventoFolha:
        try:
            await EventoFolhaRepo(session).criar(evento)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise EventoFolhaJaExiste(
                "Evento de folha já registrado (idempotência)"
            ) from exc
        await session.refresh(evento)
        return evento

    # ── 13º ─────────────────────────────────────────────────────────────

    async def registrar_13o(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        funcionario_id: UUID,
        payload: DecimoTerceiroIn,
    ) -> EventoFolha:
        _, func = await self._carregar_empresa_e_func(
            session, empresa_id, funcionario_id
        )

        # 1ª parcela é paga até 30/nov; 2ª até 20/dez.
        data_evento = (
            date(payload.ano_referencia, 11, 30)
            if payload.parcela == 1
            else date(payload.ano_referencia, 12, 20)
        )

        if await EventoFolhaRepo(session).buscar_13o(
            funcionario_id, payload.ano_referencia, payload.parcela
        ) is not None:
            raise EventoFolhaJaExiste(
                f"13º {payload.parcela}ª parcela de {payload.ano_referencia} "
                f"já registrado para o funcionário"
            )

        if payload.parcela == 1:
            r1 = calcular_13o_primeira(func.salario_base, payload.avos)
            evento = _evento_de_13o_primeira(
                tenant_id, empresa_id, funcionario_id,
                data_evento, payload.ano_referencia, r1,
            )
        else:
            primeira_paga = (
                payload.primeira_parcela_paga
                if payload.primeira_parcela_paga is not None
                else _meia_base(func.salario_base, payload.avos)
            )
            if primeira_paga < _ZERO:
                raise ParametrosFolhaInvalidos(
                    "primeira_parcela_paga não pode ser negativa"
                )
            faixas_inss, faixas_irrf = await self._tabelas_inss_irrf(
                session, data_evento
            )
            r2 = calcular_13o_segunda(
                salario=func.salario_base,
                avos=payload.avos,
                primeira_parcela_paga=primeira_paga,
                faixas_inss=faixas_inss,
                faixas_irrf=faixas_irrf,
                dependentes=func.dependentes_irrf,
            )
            evento = _evento_de_13o_segunda(
                tenant_id, empresa_id, funcionario_id,
                data_evento, payload.ano_referencia, r2,
            )

        await self._commit_evento(session, evento)
        log.info(
            "pessoal.13o.criado",
            funcionario_id=str(funcionario_id),
            ano=payload.ano_referencia,
            parcela=payload.parcela,
            avos=payload.avos,
            bruto=str(evento.valor_bruto),
            liquido=str(evento.valor_liquido),
        )
        return evento

    # ── Férias ──────────────────────────────────────────────────────────

    async def registrar_ferias(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        funcionario_id: UUID,
        payload: FeriasIn,
    ) -> EventoFolha:
        _, func = await self._carregar_empresa_e_func(
            session, empresa_id, funcionario_id
        )

        faixas_inss, faixas_irrf = await self._tabelas_inss_irrf(
            session, payload.periodo_inicio
        )
        resultado = calcular_ferias(
            salario=func.salario_base,
            dias_gozados=payload.dias_gozados,
            dias_vendidos=payload.dias_vendidos,
            faixas_inss=faixas_inss,
            faixas_irrf=faixas_irrf,
            dependentes=func.dependentes_irrf,
        )
        periodo_fim = payload.periodo_inicio + timedelta(
            days=payload.dias_gozados - 1
        )
        evento = _evento_de_ferias(
            tenant_id, empresa_id, funcionario_id,
            payload.periodo_inicio, periodo_fim, resultado,
        )
        await self._commit_evento(session, evento)
        log.info(
            "pessoal.ferias.criada",
            funcionario_id=str(funcionario_id),
            periodo_inicio=payload.periodo_inicio.isoformat(),
            dias_gozados=payload.dias_gozados,
            dias_vendidos=payload.dias_vendidos,
            liquido=str(evento.valor_liquido),
        )
        return evento

    # ── Rescisão ────────────────────────────────────────────────────────

    async def registrar_rescisao(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        funcionario_id: UUID,
        payload: RescisaoIn,
    ) -> EventoFolha:
        _, func = await self._carregar_empresa_e_func(
            session, empresa_id, funcionario_id
        )

        if func.data_demissao is not None or not func.ativo:
            raise FuncionarioJaDemitido(
                f"Funcionário {funcionario_id} já está demitido em "
                f"{func.data_demissao}"
            )
        if payload.data_demissao < func.data_admissao:
            raise ParametrosFolhaInvalidos(
                f"data_demissao ({payload.data_demissao}) anterior à "
                f"admissão ({func.data_admissao})"
            )
        if await EventoFolhaRepo(session).buscar_rescisao(
            funcionario_id
        ) is not None:
            raise EventoFolhaJaExiste(
                f"Rescisão já registrada para o funcionário {funcionario_id}"
            )

        anos = _anos_completos(func.data_admissao, payload.data_demissao)
        faixas_inss, faixas_irrf = await self._tabelas_inss_irrf(
            session, payload.data_demissao
        )
        resultado = calcular_rescisao(
            tipo=RescisaoTipo(payload.tipo.value),
            salario=func.salario_base,
            anos_completos_servico=anos,
            dias_trabalhados_mes_demissao=payload.dias_trabalhados_mes_demissao,
            avos_13o=payload.avos_13o,
            avos_ferias_proporcionais=payload.avos_ferias_proporcionais,
            ferias_vencidas_dias=payload.ferias_vencidas_dias,
            saldo_fgts_acumulado=payload.saldo_fgts_acumulado,
            faixas_inss=faixas_inss,
            faixas_irrf=faixas_irrf,
            dependentes=func.dependentes_irrf,
        )
        evento = _evento_de_rescisao(
            tenant_id, empresa_id, funcionario_id,
            payload.data_demissao, resultado,
        )

        # Side-effect: marcar funcionário como demitido. Single commit.
        try:
            await EventoFolhaRepo(session).criar(evento)
            func.data_demissao = payload.data_demissao
            func.ativo = False
            func.atualizado_em = datetime.now(tz=func.criado_em.tzinfo)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise EventoFolhaJaExiste(
                "Rescisão já registrada para o funcionário"
            ) from exc
        await session.refresh(evento)

        log.info(
            "pessoal.rescisao.criada",
            funcionario_id=str(funcionario_id),
            tipo=payload.tipo.value,
            data_demissao=payload.data_demissao.isoformat(),
            anos_servico=anos,
            bruto=str(evento.valor_bruto),
            multa_fgts=str(evento.multa_fgts),
            liquido=str(evento.valor_liquido),
        )
        return evento


# ── Helpers privados ─────────────────────────────────────────────────────


def _meia_base(salario: Decimal, avos: int) -> Decimal:
    return (salario * Decimal(avos) / Decimal("12") / _DOIS).quantize(
        Decimal("0.01")
    )


def _anos_completos(inicio: date, fim: date) -> int:
    """Anos completos entre admissão e demissão (CLT — apenas aniversários)."""
    delta = fim.year - inicio.year
    aniversario_este_ano = (fim.month, fim.day) >= (inicio.month, inicio.day)
    return max(0, delta if aniversario_este_ano else delta - 1)


def _detalhes_jsonb(obj: Any) -> JsonObject:  # noqa: ANN401 — dataclass arbitrário
    """Converte dataclasses aninhadas em dict JSON-safe (Decimal → str)."""
    raw = asdict(obj)
    serializado = _stringify(raw)
    assert isinstance(serializado, dict)
    return serializado


def _stringify(o: Any) -> Any:  # noqa: ANN401 — helper recursivo dinâmico
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, dict):
        return {k: _stringify(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_stringify(x) for x in o]
    if isinstance(o, date):
        return o.isoformat()
    return o


def _evento_de_13o_primeira(
    tenant_id: UUID,
    empresa_id: UUID,
    funcionario_id: UUID,
    data_evento: date,
    ano: int,
    r: Resultado13oPrimeira,
) -> EventoFolha:
    return EventoFolha(
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        funcionario_id=funcionario_id,
        tipo="13_primeira",
        data_evento=data_evento,
        ano_referencia=ano,
        valor_bruto=r.valor_primeira_parcela,
        inss_empregado=_ZERO,
        irrf=_ZERO,
        fgts_empregador=_ZERO,
        multa_fgts=_ZERO,
        valor_liquido=r.valor_primeira_parcela,
        detalhes=_detalhes_jsonb(r),
        algoritmo_versao=r.algoritmo_versao,
    )


def _evento_de_13o_segunda(
    tenant_id: UUID,
    empresa_id: UUID,
    funcionario_id: UUID,
    data_evento: date,
    ano: int,
    r: Resultado13oSegunda,
) -> EventoFolha:
    return EventoFolha(
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        funcionario_id=funcionario_id,
        tipo="13_segunda",
        data_evento=data_evento,
        ano_referencia=ano,
        valor_bruto=r.base_proporcional - r.primeira_parcela_paga,
        inss_empregado=r.inss.inss,
        irrf=r.irrf.irrf,
        fgts_empregador=_ZERO,
        multa_fgts=_ZERO,
        valor_liquido=r.valor_segunda_parcela,
        detalhes=_detalhes_jsonb(r),
        algoritmo_versao=r.algoritmo_versao,
    )


def _evento_de_ferias(
    tenant_id: UUID,
    empresa_id: UUID,
    funcionario_id: UUID,
    periodo_inicio: date,
    periodo_fim: date,
    r: ResultadoFerias,
) -> EventoFolha:
    return EventoFolha(
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        funcionario_id=funcionario_id,
        tipo="ferias",
        data_evento=periodo_inicio,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        valor_bruto=r.bruto_tributavel + r.abono_pecuniario,
        inss_empregado=r.inss.inss,
        irrf=r.irrf.irrf,
        fgts_empregador=_ZERO,
        multa_fgts=_ZERO,
        valor_liquido=r.valor_liquido,
        detalhes=_detalhes_jsonb(r),
        algoritmo_versao=r.algoritmo_versao,
    )


def _evento_de_rescisao(
    tenant_id: UUID,
    empresa_id: UUID,
    funcionario_id: UUID,
    data_demissao: date,
    r: ResultadoRescisao,
) -> EventoFolha:
    return EventoFolha(
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        funcionario_id=funcionario_id,
        tipo="rescisao",
        data_evento=data_demissao,
        valor_bruto=r.verbas.valor_bruto_total,
        inss_empregado=r.inss_saldo.inss + (
            r.inss_13o.inss if r.inss_13o else _ZERO
        ),
        irrf=r.irrf_saldo.irrf + (r.irrf_13o.irrf if r.irrf_13o else _ZERO),
        fgts_empregador=r.fgts_rescisao,
        multa_fgts=r.multa_fgts,
        valor_liquido=r.valor_liquido_a_pagar,
        detalhes=_detalhes_jsonb(r),
        algoritmo_versao=r.algoritmo_versao,
    )
