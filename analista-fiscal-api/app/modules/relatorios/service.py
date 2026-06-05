"""Service — relatórios contábeis (Sprint 12 PR1)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.plano_referencial import (
    codigo as conta_codigo,
    codigos_do_grupo,
)
from app.modules.empresa.repo import EmpresaRepo
from app.modules.fiscal.snapshots import parse_apuracao_output
from app.modules.relatorios.calcula_balanco import calcular_balanco
from app.modules.relatorios.calcula_dfc import EntradaDfc, calcular_dfc
from app.modules.relatorios.calcula_dre import calcular_dre
from app.modules.relatorios.calcula_dre_aux_lp import (
    ApuracaoFiscalInput,
    EntradaDreAuxLp,
    calcular_dre_aux_lp,
)
from app.modules.relatorios.calcula_indicadores import calcular_indicadores
from app.modules.relatorios.repo import (
    RelatorioRepo,
    SaldosPeriodoRepo,
)
from app.modules.relatorios.schemas import (
    GerarBalancoIn,
    GerarDfcIn,
    GerarDreAuxLpIn,
    GerarDreIn,
    GerarIndicadoresIn,
)
from app.shared.db.models import ApuracaoFiscal, RelatorioGerado
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    SemDadosContabeis,
)

log = structlog.get_logger(__name__)


class RelatoriosService:
    async def gerar_dre(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: GerarDreIn,
    ) -> RelatorioGerado:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if payload.periodo_fim < payload.periodo_inicio:
            raise ValueError("periodo_fim deve ser ≥ periodo_inicio")

        relatorio_repo = RelatorioRepo(session)
        ativo = await relatorio_repo.ativo(
            empresa_id, "dre", payload.periodo_inicio, payload.periodo_fim,
        )
        if ativo is not None and not payload.forcar_regerar:
            return ativo

        saldos_repo = SaldosPeriodoRepo(session)
        saldos = await saldos_repo.movimento_resultado_periodo(
            empresa_id, payload.periodo_inicio, payload.periodo_fim,
        )
        if not saldos:
            raise SemDadosContabeis(
                f"Sem movimentação contábil entre {payload.periodo_inicio} "
                f"e {payload.periodo_fim} para a empresa"
            )

        irpj_csll = await saldos_repo.irpj_csll_apurado_no_periodo(
            empresa_id, payload.periodo_inicio, payload.periodo_fim,
        )

        resultado = calcular_dre(
            saldos,
            irpj_csll_apurado=irpj_csll,
            resultado_financeiro=payload.resultado_financeiro,
        )

        novo = RelatorioGerado(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="dre",
            periodo_inicio=payload.periodo_inicio,
            periodo_fim=payload.periodo_fim,
            payload=_stringify(asdict(resultado)),
            saldos_base=_stringify(
                {
                    "saldos": [
                        {
                            "codigo": s.codigo,
                            "descricao": s.descricao,
                            "saldo_final": s.saldo_final,
                        }
                        for s in saldos
                    ],
                    "irpj_csll_apurado": irpj_csll,
                    "resultado_financeiro": payload.resultado_financeiro,
                }
            ),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await relatorio_repo.criar(novo)

        if ativo is not None:
            await relatorio_repo.marcar_superseded(ativo, novo.id)

        await session.commit()
        await session.refresh(novo)

        log.info(
            "relatorios.dre.gerado",
            empresa_id=str(empresa_id),
            periodo_inicio=payload.periodo_inicio.isoformat(),
            periodo_fim=payload.periodo_fim.isoformat(),
            lucro_liquido=str(resultado.lucro_liquido.valor),
            superseded=str(ativo.id) if ativo else None,
        )
        return novo


    async def gerar_balanco(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: GerarBalancoIn,
    ) -> RelatorioGerado:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        relatorio_repo = RelatorioRepo(session)
        ativo = await relatorio_repo.ativo(
            empresa_id, "balanco",
            payload.data_referencia, payload.data_referencia,
        )
        if ativo is not None and not payload.forcar_regerar:
            return ativo

        saldos_repo = SaldosPeriodoRepo(session)
        saldos = await saldos_repo.saldos_posicao_em(
            empresa_id, payload.data_referencia,
        )
        if not saldos:
            raise SemDadosContabeis(
                f"Sem saldos contábeis até {payload.data_referencia} para a empresa"
            )

        resultado = calcular_balanco(saldos)
        novo = RelatorioGerado(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="balanco",
            periodo_inicio=payload.data_referencia,
            periodo_fim=payload.data_referencia,
            payload=_stringify(asdict(resultado)),
            saldos_base=_stringify(
                {
                    "saldos": [
                        {
                            "codigo": s.codigo,
                            "descricao": s.descricao,
                            "natureza": s.natureza,
                            "tipo": s.tipo,
                            "saldo_final": s.saldo_final,
                        }
                        for s in saldos
                    ],
                }
            ),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await relatorio_repo.criar(novo)
        if ativo is not None:
            await relatorio_repo.marcar_superseded(ativo, novo.id)
        await session.commit()
        await session.refresh(novo)

        log.info(
            "relatorios.balanco.gerado",
            empresa_id=str(empresa_id),
            data_ref=payload.data_referencia.isoformat(),
            ativo_total=str(resultado.ativo_total.valor),
            fecha=resultado.fecha,
            diferenca=str(resultado.diferenca),
        )
        return novo

    async def gerar_dfc(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: GerarDfcIn,
    ) -> RelatorioGerado:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if payload.periodo_fim < payload.periodo_inicio:
            raise ValueError("periodo_fim deve ser ≥ periodo_inicio")

        relatorio_repo = RelatorioRepo(session)
        ativo = await relatorio_repo.ativo(
            empresa_id, "dfc", payload.periodo_inicio, payload.periodo_fim,
        )
        if ativo is not None and not payload.forcar_regerar:
            return ativo

        saldos_repo = SaldosPeriodoRepo(session)

        # Lucro Líquido: deriva do DRE do mesmo período.
        saldos_dre = await saldos_repo.movimento_resultado_periodo(
            empresa_id, payload.periodo_inicio, payload.periodo_fim,
        )
        if not saldos_dre:
            raise SemDadosContabeis(
                f"Sem movimentação contábil de resultado entre "
                f"{payload.periodo_inicio} e {payload.periodo_fim}"
            )
        irpj_csll = await saldos_repo.irpj_csll_apurado_no_periodo(
            empresa_id, payload.periodo_inicio, payload.periodo_fim,
        )
        dre = calcular_dre(saldos_dre, irpj_csll_apurado=irpj_csll)

        # Não-caixa: depreciação do período (acumulada na conta de despesa).
        depreciacao = await saldos_repo.soma_movimento_codigo_periodo(
            empresa_id,
            conta_codigo("despesa_depreciacao"),
            payload.periodo_inicio,
            payload.periodo_fim,
        )

        # Variações de saldos finais (fim − início do período).
        # Códigos vêm de `plano_referencial.GRUPOS_CONTABEIS` — fonte canônica única.
        # FIX #9 (PR6): buscamos os saldos posicao_em UMA VEZ para cada snapshot
        # (fim e antes) e indexamos por código em memória — elimina o N+1 de antes
        # (~12 chamadas individuais × 2 = ~24 queries → 2 queries).
        antes = _date_anterior(payload.periodo_inicio)
        cod_clientes = codigos_do_grupo("clientes")
        cod_estoques = codigos_do_grupo("estoques")
        cod_fornec = codigos_do_grupo("fornecedores")
        cod_encargos = codigos_do_grupo("encargos_a_pagar")
        cod_imob = codigos_do_grupo("imobilizado_bruto")
        cod_caixa = codigos_do_grupo("caixa_equivalentes")

        saldos_fim_list = await saldos_repo.saldos_posicao_em(empresa_id, payload.periodo_fim)
        saldos_ant_list = await saldos_repo.saldos_posicao_em(empresa_id, antes)
        saldos_fim_idx: dict[str, Decimal] = {s.codigo: s.saldo_final for s in saldos_fim_list}
        saldos_ant_idx: dict[str, Decimal] = {s.codigo: s.saldo_final for s in saldos_ant_list}

        _zero = Decimal("0")

        def _soma_grupo_fim(codigos: tuple[str, ...]) -> Decimal:
            return sum((saldos_fim_idx.get(c, _zero) for c in codigos), _zero)

        def _soma_grupo_ant(codigos: tuple[str, ...]) -> Decimal:
            return sum((saldos_ant_idx.get(c, _zero) for c in codigos), _zero)

        clientes_fim = _soma_grupo_fim(cod_clientes)
        clientes_ini = _soma_grupo_ant(cod_clientes)
        estoques_fim = _soma_grupo_fim(cod_estoques)
        estoques_ini = _soma_grupo_ant(cod_estoques)
        fornec_fim = _soma_grupo_fim(cod_fornec)
        fornec_ini = _soma_grupo_ant(cod_fornec)
        encargos_fim = _soma_grupo_fim(cod_encargos)
        encargos_ini = _soma_grupo_ant(cod_encargos)
        imob_fim = _soma_grupo_fim(cod_imob)
        imob_ini = _soma_grupo_ant(cod_imob)
        caixa_fim = _soma_grupo_fim(cod_caixa)
        caixa_ini = _soma_grupo_ant(cod_caixa)

        entrada = EntradaDfc(
            lucro_liquido=dre.lucro_liquido.valor,
            depreciacao_periodo=depreciacao,
            provisoes_constituidas=Decimal("0"),  # MVP — provisões não isoladas
            variacao_clientes=clientes_fim - clientes_ini,
            variacao_estoques=estoques_fim - estoques_ini,
            variacao_fornecedores=fornec_fim - fornec_ini,
            variacao_encargos_a_pagar=encargos_fim - encargos_ini,
            aquisicao_imobilizado=max(imob_fim - imob_ini, Decimal("0")),
            venda_imobilizado=max(imob_ini - imob_fim, Decimal("0")),
            aporte_capital=payload.aporte_capital,
            emprestimos_captados=payload.emprestimos_captados,
            emprestimos_pagos=payload.emprestimos_pagos,
            distribuicao_lucros=payload.distribuicao_lucros,
            saldo_caixa_inicial=caixa_ini,
            saldo_caixa_final=caixa_fim,
        )
        resultado = calcular_dfc(entrada)

        novo = RelatorioGerado(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="dfc",
            periodo_inicio=payload.periodo_inicio,
            periodo_fim=payload.periodo_fim,
            payload=_stringify(asdict(resultado)),
            saldos_base=_stringify(asdict(entrada)),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await relatorio_repo.criar(novo)
        if ativo is not None:
            await relatorio_repo.marcar_superseded(ativo, novo.id)
        await session.commit()
        await session.refresh(novo)

        log.info(
            "relatorios.dfc.gerado",
            empresa_id=str(empresa_id),
            periodo_inicio=payload.periodo_inicio.isoformat(),
            periodo_fim=payload.periodo_fim.isoformat(),
            op=str(resultado.caixa_operacional.valor),
            inv=str(resultado.caixa_investimento.valor),
            fin=str(resultado.caixa_financiamento.valor),
            fecha=resultado.fecha,
        )
        return novo


    async def gerar_indicadores(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: GerarIndicadoresIn,
    ) -> RelatorioGerado:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        relatorio_repo = RelatorioRepo(session)
        ativo = await relatorio_repo.ativo(
            empresa_id, "indicadores",
            payload.periodo_inicio, payload.periodo_fim,
        )
        if ativo is not None and not payload.forcar_regerar:
            return ativo

        # Reusa DRE do período.
        saldos_repo = SaldosPeriodoRepo(session)
        saldos_dre = await saldos_repo.movimento_resultado_periodo(
            empresa_id, payload.periodo_inicio, payload.periodo_fim,
        )
        if not saldos_dre:
            raise SemDadosContabeis(
                f"Sem movimentação contábil entre {payload.periodo_inicio} "
                f"e {payload.periodo_fim}"
            )
        irpj_csll = await saldos_repo.irpj_csll_apurado_no_periodo(
            empresa_id, payload.periodo_inicio, payload.periodo_fim,
        )
        dre = calcular_dre(saldos_dre, irpj_csll_apurado=irpj_csll)

        # Reusa Balanço na data_referencia = periodo_fim.
        saldos_pos = await saldos_repo.saldos_posicao_em(
            empresa_id, payload.periodo_fim,
        )
        if not saldos_pos:
            raise SemDadosContabeis(
                f"Sem saldos contábeis até {payload.periodo_fim}"
            )
        balanco = calcular_balanco(saldos_pos)

        resultado = calcular_indicadores(balanco, dre)
        novo = RelatorioGerado(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="indicadores",
            periodo_inicio=payload.periodo_inicio,
            periodo_fim=payload.periodo_fim,
            payload=_stringify(asdict(resultado)),
            saldos_base=_stringify(
                {
                    "balanco_resumo": {
                        "ativo_total": balanco.ativo_total.valor,
                        "passivo_total": balanco.passivo_circulante.valor
                        + balanco.passivo_nao_circulante.valor,
                        "pl": balanco.patrimonio_liquido.valor,
                    },
                    "dre_resumo": {
                        "receita_liquida": dre.receita_liquida.valor,
                        "lucro_bruto": dre.lucro_bruto.valor,
                        "ebitda": dre.ebitda.valor,
                        "lucro_liquido": dre.lucro_liquido.valor,
                    },
                }
            ),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await relatorio_repo.criar(novo)
        if ativo is not None:
            await relatorio_repo.marcar_superseded(ativo, novo.id)
        await session.commit()
        await session.refresh(novo)

        log.info(
            "relatorios.indicadores.gerado",
            empresa_id=str(empresa_id),
            periodo_inicio=payload.periodo_inicio.isoformat(),
            periodo_fim=payload.periodo_fim.isoformat(),
            liquidez_corrente=str(resultado.liquidez_corrente.valor),
            margem_liquida=str(resultado.margem_liquida.valor),
            roe=str(resultado.roe.valor),
        )
        return novo

    async def gerar_dre_aux_lp(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: GerarDreAuxLpIn,
    ) -> RelatorioGerado:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        periodo_inicio, periodo_fim = _data_trimestre(payload.ano, payload.trimestre)

        relatorio_repo = RelatorioRepo(session)
        ativo = await relatorio_repo.ativo(
            empresa_id, "dre_aux_lp", periodo_inicio, periodo_fim,
        )
        if ativo is not None and not payload.forcar_regerar:
            return ativo

        # Recupera apurações do trimestre.
        saldos_repo = SaldosPeriodoRepo(session)
        apuracoes_orm = await saldos_repo.apuracoes_do_trimestre(
            empresa_id, periodo_inicio, periodo_fim,
        )
        apuracoes_in = [_to_apuracao_input(ap) for ap in apuracoes_orm]

        # Recupera DRE contábil do trimestre.
        saldos_dre = await saldos_repo.movimento_resultado_periodo(
            empresa_id, periodo_inicio, periodo_fim,
        )
        if not saldos_dre and not apuracoes_in:
            raise SemDadosContabeis(
                f"Sem movimentação contábil nem apurações fiscais em "
                f"{payload.ano}-T{payload.trimestre}"
            )
        irpj_csll = await saldos_repo.irpj_csll_apurado_no_periodo(
            empresa_id, periodo_inicio, periodo_fim,
        )
        dre = calcular_dre(saldos_dre, irpj_csll_apurado=irpj_csll)

        entrada = EntradaDreAuxLp(
            ano=payload.ano,
            trimestre=payload.trimestre,
            receita_bruta_contabil=dre.receita_bruta.valor,
            receita_liquida_contabil=dre.receita_liquida.valor,
            lucro_liquido_contabil=dre.lucro_liquido.valor,
            apuracoes=apuracoes_in,
        )
        resultado = calcular_dre_aux_lp(entrada)

        novo = RelatorioGerado(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="dre_aux_lp",
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            payload=_stringify(asdict(resultado)),
            saldos_base=_stringify(asdict(entrada)),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await relatorio_repo.criar(novo)
        if ativo is not None:
            await relatorio_repo.marcar_superseded(ativo, novo.id)
        await session.commit()
        await session.refresh(novo)

        log.info(
            "relatorios.dre_aux_lp.gerado",
            empresa_id=str(empresa_id),
            ano=payload.ano,
            trimestre=payload.trimestre,
            total_tributos=str(resultado.total_tributos),
            carga=str(resultado.carga_tributaria_efetiva),
            diferenca_receita=str(resultado.diferenca_receita),
        )
        return novo


def _data_trimestre(ano: int, trimestre: int) -> tuple[date, date]:
    """(periodo_inicio, periodo_fim) — primeiro dia do trimestre + último dia."""
    mes_inicial = {1: 1, 2: 4, 3: 7, 4: 10}[trimestre]
    inicio = date(ano, mes_inicial, 1)
    # Último dia do trimestre = último dia do 3º mês.
    mes_final = mes_inicial + 2
    dias = {1: 31, 4: 30, 7: 31, 10: 31}[mes_inicial]
    return inicio, date(ano, mes_final, dias)


def _to_apuracao_input(ap: ApuracaoFiscal) -> ApuracaoFiscalInput:
    """Converte ``ApuracaoFiscal`` ORM → input do algoritmo puro.

    Usa `parse_apuracao_output` (Pydantic discriminator) — fonte canônica
    de schema. Adicionar tipo novo de tributo = registrar Snapshot no
    discriminator, não tocar este código.
    """
    snap = parse_apuracao_output(ap.tipo, ap.output_jsonb, input_jsonb=ap.input_jsonb)
    return ApuracaoFiscalInput(
        tipo=ap.tipo,
        valor=snap.valor_devido,
        base_calculo=snap.base_calculo,
    )


async def _soma_saldos_codigos(
    repo: SaldosPeriodoRepo,
    empresa_id: UUID,
    codigos: tuple[str, ...],
    em: date,
) -> Decimal:
    total = Decimal("0")
    for c in codigos:
        total += await repo.saldo_conta_codigo_em(empresa_id, c, em)
    return total


def _date_anterior(d: date) -> date:
    """Último dia do mês anterior a ``d`` — para snapshot de saldo inicial."""
    from datetime import timedelta

    return d - timedelta(days=1)


def _stringify(o: Any) -> Any:  # noqa: ANN401 — helper recursivo dinâmico
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: _stringify(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_stringify(x) for x in o]
    return o
