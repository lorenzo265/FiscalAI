"""Service de sócio, pró-labore, distribuição e eSocial (Sprint 10 PR3)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.shared.types import JsonObject
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.pessoal.calcula_distribuicao import (
    BaseCalculoReferencia,
    calcular_distribuicao,
)
from app.modules.pessoal.calcula_prolabore import calcular_prolabore
from app.modules.pessoal.esocial_payloads import (
    AdmissaoInput,
    DesligamentoInput,
    EmpregadorInput,
    HoleriteInput,
    PagamentoInput,
    TrabalhadorInput,
    gerar_s1200_remuneracao,
    gerar_s1210_pagamento,
    gerar_s2200_admissao,
    gerar_s2299_desligamento,
    gerar_s2300_inicio_tsve,
)
from app.modules.pessoal.repo import (
    DistribuicaoRepo,
    EventoESocialRepo,
    EventoFolhaRepo,
    FuncionarioRepo,
    HoleriteRepo,
    ProlaboreRepo,
    SocioRepo,
    TabelasTributariasRepo,
)
from app.modules.pessoal.schemas import (
    DistribuicaoIn,
    EsocialGerarIn,
    ProlaboreIn,
    SocioIn,
    TipoEventoESocialIn,
)
from app.shared.db.models import (
    DistribuicaoLucros,
    Empresa,
    EventoESocial,
    EventoFolha,
    Funcionario,
    Holerite,
    ProlaboreMensal,
    Socio,
)
from app.shared.exceptions import (
    CpfSocioJaCadastrado,
    DistribuicaoInvalida,
    EmpresaNaoEncontrada,
    EventoESocialJaExiste,
    FuncionarioNaoEncontrado,
    ParametrosFolhaInvalidos,
    ProlaboreJaRegistrado,
    SocioNaoEncontrado,
    TabelaTributariaAusente,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_ZERO = Decimal("0.00")


class SocioService:
    async def cadastrar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: SocioIn,
    ) -> Socio:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        repo = SocioRepo(session)
        if await repo.cpf_existe(empresa_id, payload.cpf):
            raise CpfSocioJaCadastrado(
                f"CPF {payload.cpf} já cadastrado como sócio nesta empresa"
            )

        socio = Socio(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            nome=payload.nome,
            cpf=payload.cpf,
            percentual_participacao=payload.percentual_participacao,
            data_entrada=payload.data_entrada,
            dependentes_irrf=payload.dependentes_irrf,
        )
        try:
            await repo.criar(socio)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise CpfSocioJaCadastrado(
                f"CPF {payload.cpf} já cadastrado como sócio"
            ) from exc

        log.info(
            "pessoal.socio.criado",
            socio_id=str(socio.id),
            empresa_id=str(empresa_id),
            participacao=str(socio.percentual_participacao),
        )
        return socio


class ProlaboreService:
    async def registrar_mensal(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        socio_id: UUID,
        payload: ProlaboreIn,
    ) -> ProlaboreMensal:
        empresa, socio = await _carregar_empresa_socio(session, empresa_id, socio_id)
        comp_dia1 = date(payload.competencia.year, payload.competencia.month, 1)

        if await ProlaboreRepo(session).por_competencia(socio_id, comp_dia1):
            raise ProlaboreJaRegistrado(
                f"Pró-labore de {comp_dia1.isoformat()} já registrado para o sócio"
            )

        tabelas = TabelasTributariasRepo(session)
        teto = await tabelas.teto_inss_contribuinte_individual_vigente(comp_dia1)
        if teto is None:
            raise TabelaTributariaAusente(
                f"Teto INSS contribuinte individual ausente em {comp_dia1}"
            )
        faixas_irrf = await tabelas.irrf_faixas_vigentes(comp_dia1)
        if len(faixas_irrf) != 5:
            raise TabelaTributariaAusente(
                f"Tabela IRRF incompleta em {comp_dia1.isoformat()}"
            )

        resultado = calcular_prolabore(
            valor_bruto=payload.valor_bruto,
            teto_previdenciario=teto,
            faixas_irrf=faixas_irrf,
            dependentes=socio.dependentes_irrf,
            aliquota_inss=payload.aliquota_inss,
        )

        prolabore = ProlaboreMensal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            socio_id=socio_id,
            competencia=comp_dia1,
            valor_bruto=resultado.valor_bruto,
            base_inss=resultado.base_inss,
            aliquota_inss=resultado.aliquota_inss,
            inss_socio=resultado.inss_socio,
            base_irrf=resultado.irrf.base_irrf,
            irrf=resultado.irrf.irrf,
            irrf_faixa=resultado.irrf.faixa,
            valor_liquido=resultado.valor_liquido,
            algoritmo_versao=resultado.algoritmo_versao,
        )
        try:
            await ProlaboreRepo(session).criar(prolabore)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ProlaboreJaRegistrado(
                "Pró-labore (sócio, competência) já registrado"
            ) from exc
        await session.refresh(prolabore)

        log.info(
            "pessoal.prolabore.criado",
            socio_id=str(socio_id),
            competencia=comp_dia1.isoformat(),
            bruto=str(resultado.valor_bruto),
            inss=str(resultado.inss_socio),
            irrf=str(resultado.irrf.irrf),
            liquido=str(resultado.valor_liquido),
        )
        return prolabore


class DistribuicaoService:
    async def registrar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        socio_id: UUID,
        payload: DistribuicaoIn,
    ) -> DistribuicaoLucros:
        _, socio = await _carregar_empresa_socio(session, empresa_id, socio_id)

        faixas_irrf = await TabelasTributariasRepo(session).irrf_faixas_vigentes(
            payload.data_distribuicao
        )
        if len(faixas_irrf) != 5:
            raise TabelaTributariaAusente(
                f"Tabela IRRF incompleta em {payload.data_distribuicao.isoformat()}"
            )

        # Sprint 19.7 PR1 (#15): limite_isento_apurado None = service
        # calcula automaticamente. Caller pode override passando valor.
        if payload.limite_isento_apurado is None:
            limite_isento_apurado = (
                await self._apurar_limite_isento_automatico(
                    session,
                    empresa_id=empresa_id,
                    data_distribuicao=payload.data_distribuicao,
                    base_calculo_referencia=BaseCalculoReferencia(
                        payload.base_calculo_referencia.value
                    ),
                )
            )
        else:
            limite_isento_apurado = payload.limite_isento_apurado

        try:
            resultado = calcular_distribuicao(
                valor_distribuido=payload.valor,
                limite_isento_apurado=limite_isento_apurado,
                base_calculo_referencia=BaseCalculoReferencia(
                    payload.base_calculo_referencia.value
                ),
                faixas_irrf=faixas_irrf,
                dependentes=socio.dependentes_irrf,
            )
        except ValueError as exc:
            raise DistribuicaoInvalida(str(exc)) from exc

        distribuicao = DistribuicaoLucros(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            socio_id=socio_id,
            data_distribuicao=payload.data_distribuicao,
            valor=resultado.valor_distribuido,
            limite_isento_apurado=resultado.limite_isento_apurado,
            valor_isento=resultado.valor_isento,
            valor_tributavel=resultado.valor_tributavel,
            irrf_retido=resultado.irrf_retido,
            base_calculo_referencia=payload.base_calculo_referencia.value,
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await DistribuicaoRepo(session).criar(distribuicao)
        await session.commit()
        await session.refresh(distribuicao)

        log.info(
            "pessoal.distribuicao.criada",
            socio_id=str(socio_id),
            data=payload.data_distribuicao.isoformat(),
            valor=str(payload.valor),
            isento=str(resultado.valor_isento),
            tributavel=str(resultado.valor_tributavel),
            irrf=str(resultado.irrf_retido),
        )
        return distribuicao

    async def _apurar_limite_isento_automatico(
        self,
        session: AsyncSession,
        *,
        empresa_id: UUID,
        data_distribuicao: date,
        base_calculo_referencia: BaseCalculoReferencia,
    ) -> Decimal:
        """Sprint 19.7 PR1 (#15) — limite isento automático.

        Calcula baseado no regime declarado em
        ``base_calculo_referencia``:

          * ``PRESUNCAO_LP``: receita do trimestre × presunção CNAE
            (``presuncao_lucro_presumido`` SCD) - IRPJ+CSLL+PIS+COFINS
            pagos no trimestre.
          * ``SIMPLES_DENTRO_DAS``: receita do ano × presunção do anexo -
            DAS recolhido no ano.
          * ``MEI`` / ``LUCRO_CONTABIL``: sem dados estruturados pra
            calcular — retorna 0 (admin precisa informar manualmente).

        Defensivo: qualquer erro (sem dados, sem CNAE, sem apurações)
        cai em 0 e loga warning — distribuição continua mas vira 100%
        tributada (cliente revisa no painel).
        """
        from app.modules.lucro_presumido.repo import PresuncaoLpRepo
        from app.modules.pessoal.calcula_limite_isento import (
            _ZERO as _ZERO_LIMITE,
            calcular_limite_isento_lucro_presumido,
            calcular_limite_isento_simples_nacional,
        )
        from app.shared.db.models import ApuracaoFiscal, Empresa
        from sqlalchemy import select

        empresa = (
            await session.execute(
                select(Empresa).where(Empresa.id == empresa_id)
            )
        ).scalar_one_or_none()
        if empresa is None:
            return _ZERO_LIMITE

        if base_calculo_referencia is BaseCalculoReferencia.PRESUNCAO_LP:
            return await self._limite_isento_lp(
                session, empresa, data_distribuicao
            )
        if base_calculo_referencia is BaseCalculoReferencia.SIMPLES_DENTRO_DAS:
            return await self._limite_isento_sn(
                session, empresa, data_distribuicao
            )
        # MEI / LUCRO_CONTABIL — sem rotina automática hoje.
        log.info(
            "pessoal.distribuicao.limite_isento_manual",
            empresa_id=str(empresa.id),
            base=base_calculo_referencia.value,
        )
        return _ZERO_LIMITE

    async def _limite_isento_lp(
        self,
        session: AsyncSession,
        empresa: "Empresa",
        data: date,
    ) -> Decimal:
        from app.modules.lucro_presumido.repo import PresuncaoLpRepo
        from app.modules.pessoal.calcula_limite_isento import (
            _ZERO as _ZERO_LIMITE,
            calcular_limite_isento_lucro_presumido,
        )
        from app.shared.db.models import ApuracaoFiscal
        from sqlalchemy import select

        # Período do trimestre — 1º dia do trimestre até último dia do trimestre.
        trimestre = (data.month - 1) // 3 + 1
        mes_inicio = (trimestre - 1) * 3 + 1
        periodo_inicio = date(data.year, mes_inicio, 1)
        mes_fim = mes_inicio + 2
        # Último dia do trimestre — usa primeiro dia do trimestre seguinte
        # menos 1.
        if mes_fim == 12:
            periodo_fim_excl = date(data.year + 1, 1, 1)
        else:
            periodo_fim_excl = date(data.year, mes_fim + 1, 1)

        presuncao = await PresuncaoLpRepo(session).resolver_por_cnae(
            data,
            empresa.cnae_principal,
            faturamento_12m=empresa.faturamento_12m,
        )
        if presuncao is None:
            log.warning(
                "pessoal.distribuicao.presuncao_lp_ausente",
                empresa_id=str(empresa.id),
                cnae=empresa.cnae_principal,
            )
            return _ZERO_LIMITE

        # Apura receita e impostos pagos do trimestre.
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa.id)
            .where(ApuracaoFiscal.competencia >= periodo_inicio)
            .where(ApuracaoFiscal.competencia < periodo_fim_excl)
        )
        apuracoes = list(
            (await session.execute(stmt)).scalars().all()
        )
        receita_total = _ZERO_LIMITE
        irpj = _ZERO_LIMITE
        csll = _ZERO_LIMITE
        pis = _ZERO_LIMITE
        cofins = _ZERO_LIMITE
        for ap in apuracoes:
            out = ap.output_jsonb or {}
            receita_total += Decimal(str(out.get("receita_periodo", "0")))
            valor = Decimal(str(out.get("valor", "0")))
            if ap.tipo == "irpj":
                irpj += valor
            elif ap.tipo == "csll":
                csll += valor
            elif ap.tipo == "pis":
                pis += valor
            elif ap.tipo == "cofins":
                cofins += valor
        if receita_total <= _ZERO_LIMITE:
            return _ZERO_LIMITE
        calc = calcular_limite_isento_lucro_presumido(
            receita_periodo=receita_total,
            presuncao_irpj=presuncao.percentual_irpj,
            irpj_pago=irpj,
            csll_pago=csll,
            pis_pago=pis,
            cofins_pago=cofins,
        )
        log.info(
            "pessoal.distribuicao.limite_isento_lp",
            empresa_id=str(empresa.id),
            trimestre=f"{data.year}-T{trimestre}",
            limite=str(calc.limite_isento),
            receita=str(calc.receita_periodo),
        )
        return calc.limite_isento

    async def _limite_isento_sn(
        self,
        session: AsyncSession,
        empresa: "Empresa",
        data: date,
    ) -> Decimal:
        from app.modules.pessoal.calcula_limite_isento import (
            _ZERO as _ZERO_LIMITE,
            calcular_limite_isento_simples_nacional,
        )
        from app.shared.db.models import ApuracaoFiscal
        from sqlalchemy import select

        # SN — apura sobre o ano-calendário corrente até o mês da
        # distribuição.
        periodo_inicio = date(data.year, 1, 1)
        if data.month == 12:
            periodo_fim_excl = date(data.year + 1, 1, 1)
        else:
            periodo_fim_excl = date(data.year, data.month + 1, 1)

        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa.id)
            .where(ApuracaoFiscal.tipo == "das")
            .where(ApuracaoFiscal.competencia >= periodo_inicio)
            .where(ApuracaoFiscal.competencia < periodo_fim_excl)
        )
        apuracoes = list(
            (await session.execute(stmt)).scalars().all()
        )
        receita_total = _ZERO_LIMITE
        das_total = _ZERO_LIMITE
        for ap in apuracoes:
            out = ap.output_jsonb or {}
            receita_total += Decimal(str(out.get("receita_mes", "0")))
            das_total += Decimal(str(out.get("valor", "0")))
        if receita_total <= _ZERO_LIMITE:
            return _ZERO_LIMITE
        anexo = empresa.anexo_simples or "III"
        calc = calcular_limite_isento_simples_nacional(
            receita_periodo=receita_total,
            anexo=anexo,
            das_pago_periodo=das_total,
        )
        log.info(
            "pessoal.distribuicao.limite_isento_sn",
            empresa_id=str(empresa.id),
            ano=data.year,
            anexo=anexo,
            limite=str(calc.limite_isento),
            receita=str(calc.receita_periodo),
        )
        return calc.limite_isento


class EsocialService:
    """Skeleton — gera payload JSON e persiste com ``status='preparado'``.

    Transmissão real à API eSocial (com certificado A1) fica para sprint
    futura. O ``payload`` JSONB já corresponde 1:1 ao XML que será emitido.
    """

    async def gerar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: EsocialGerarIn,
    ) -> EventoESocial:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if await EventoESocialRepo(session).buscar(
            empresa_id, payload.tipo_evento.value, payload.referencia_id
        ):
            raise EventoESocialJaExiste(
                f"Evento {payload.tipo_evento.value} já gerado para a referência "
                f"{payload.referencia_id}"
            )

        ref_tipo, periodo, payload_dict, algo = await _gerar_payload(
            session, empresa, payload
        )
        evento = EventoESocial(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo_evento=payload.tipo_evento.value,
            referencia_tipo=ref_tipo,
            referencia_id=payload.referencia_id,
            periodo_apuracao=periodo,
            payload=payload_dict,
            status="preparado",
            algoritmo_versao=algo,
        )
        try:
            await EventoESocialRepo(session).criar(evento)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise EventoESocialJaExiste(
                "Evento eSocial (empresa, tipo, referência) já existe"
            ) from exc
        await session.refresh(evento)

        log.info(
            "pessoal.esocial.gerado",
            evento_id=str(evento.id),
            empresa_id=str(empresa_id),
            tipo=payload.tipo_evento.value,
            referencia_id=str(payload.referencia_id),
            periodo=periodo.isoformat() if periodo else None,
        )
        return evento


# ── Helpers privados ─────────────────────────────────────────────────────


async def _carregar_empresa_socio(
    session: AsyncSession, empresa_id: UUID, socio_id: UUID
) -> tuple[Empresa, Socio]:
    empresa = await EmpresaRepo(session).por_id(empresa_id)
    if empresa is None:
        raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
    socio = await SocioRepo(session).por_id(socio_id)
    if socio is None or socio.empresa_id != empresa_id:
        raise SocioNaoEncontrado(
            f"Sócio {socio_id} não encontrado nesta empresa"
        )
    return empresa, socio


async def _gerar_payload(
    session: AsyncSession,
    empresa: Empresa,
    payload: EsocialGerarIn,
) -> tuple[str, date | None, JsonObject, str]:
    """Despacha por tipo: carrega referência + monta dict via gerador puro."""
    emp_in = EmpregadorInput(cnpj=empresa.cnpj, razao_social=empresa.razao_social)
    tipo = payload.tipo_evento

    if tipo is TipoEventoESocialIn.S_1200:
        hol = await _carregar_holerite(session, payload.referencia_id)
        func = await _carregar_funcionario_obrig(session, hol.funcionario_id)
        trab_in = _trab_input(func)
        hol_in = HoleriteInput(
            competencia=hol.competencia,
            salario_bruto=hol.salario_bruto,
            inss_empregado=hol.inss_empregado,
            irrf=hol.irrf,
            fgts_empregador=hol.fgts_empregador,
            valor_liquido=hol.valor_liquido,
        )
        return (
            "holerite",
            hol.competencia,
            gerar_s1200_remuneracao(emp_in, trab_in, hol_in),
            "esocial.skeleton.v1",
        )

    if tipo is TipoEventoESocialIn.S_1210:
        if payload.data_pagamento is None:
            raise ParametrosFolhaInvalidos(
                "S-1210 exige data_pagamento no payload"
            )
        hol = await _carregar_holerite(session, payload.referencia_id)
        func = await _carregar_funcionario_obrig(session, hol.funcionario_id)
        pag = PagamentoInput(
            data_pagamento=payload.data_pagamento,
            valor_liquido=hol.valor_liquido,
            periodo_referencia=hol.competencia,
        )
        return (
            "holerite",
            hol.competencia,
            gerar_s1210_pagamento(emp_in, _trab_input(func), pag),
            "esocial.skeleton.v1",
        )

    if tipo is TipoEventoESocialIn.S_2200:
        func = await _carregar_funcionario_obrig(session, payload.referencia_id)
        adm = AdmissaoInput(
            data_admissao=func.data_admissao,
            cargo=func.cargo,
            salario_base=func.salario_base,
            vinculo=func.vinculo,
        )
        return (
            "funcionario",
            None,
            gerar_s2200_admissao(emp_in, _trab_input(func), adm),
            "esocial.skeleton.v1",
        )

    if tipo is TipoEventoESocialIn.S_2299:
        ev = await _carregar_evento_folha(session, payload.referencia_id)
        if ev.tipo != "rescisao":
            raise ParametrosFolhaInvalidos(
                f"S-2299 exige referência a evento_folha tipo=rescisao "
                f"(recebido {ev.tipo})"
            )
        func = await _carregar_funcionario_obrig(session, ev.funcionario_id)
        motivo = str(ev.detalhes.get("tipo", "sem_justa_causa"))
        des = DesligamentoInput(
            data_desligamento=ev.data_evento,
            motivo=motivo,
            valor_bruto_verbas=ev.valor_bruto,
            saldo_fgts=Decimal(
                str(ev.detalhes.get("saldo_fgts_acumulado", "0"))
            ),
        )
        return (
            "evento_folha",
            None,
            gerar_s2299_desligamento(emp_in, _trab_input(func), des),
            "esocial.skeleton.v1",
        )

    if tipo is TipoEventoESocialIn.S_2300:
        # Sprint 19.6 PR1 (#14): substitui S-2400 (RPPS, uso adaptado) por
        # S-2300 (TSVE — evento canônico pra sócio recebendo pró-labore).
        socio = await SocioRepo(session).por_id(payload.referencia_id)
        if socio is None or socio.empresa_id != empresa.id:
            raise SocioNaoEncontrado(
                f"Sócio {payload.referencia_id} não encontrado nesta empresa"
            )
        ultimo_prolabore = await ProlaboreRepo(session).listar_do_socio(
            socio.id, limite=1
        )
        valor_ref = (
            ultimo_prolabore[0].valor_bruto
            if ultimo_prolabore else _ZERO
        )
        trab_in = TrabalhadorInput(
            cpf=socio.cpf, nome=socio.nome, data_nascimento=None,
        )
        return (
            "socio",
            None,
            gerar_s2300_inicio_tsve(
                emp_in, trab_in,
                data_inicio=socio.data_entrada,
                valor_referencia=valor_ref,
            ),
            "esocial.skeleton.v2",
        )

    raise ParametrosFolhaInvalidos(f"Tipo de evento eSocial não suportado: {tipo}")


def _trab_input(func: Funcionario) -> TrabalhadorInput:
    return TrabalhadorInput(cpf=func.cpf, nome=func.nome, data_nascimento=None)


async def _carregar_holerite(session: AsyncSession, holerite_id: UUID) -> Holerite:
    # listagem por folha não cabe — usamos query direta
    from sqlalchemy import select as _select

    stmt = _select(Holerite).where(Holerite.id == holerite_id)
    hol = (await session.execute(stmt)).scalar_one_or_none()
    if hol is None:
        raise ParametrosFolhaInvalidos(
            f"Holerite {holerite_id} não encontrado"
        )
    return hol


async def _carregar_funcionario_obrig(
    session: AsyncSession, funcionario_id: UUID
) -> Funcionario:
    func = await FuncionarioRepo(session).por_id(funcionario_id)
    if func is None:
        raise FuncionarioNaoEncontrado(
            f"Funcionário {funcionario_id} não encontrado"
        )
    return func


async def _carregar_evento_folha(
    session: AsyncSession, evento_id: UUID
) -> EventoFolha:
    ev = await EventoFolhaRepo(session).por_id(evento_id)
    if ev is None:
        raise ParametrosFolhaInvalidos(
            f"Evento de folha {evento_id} não encontrado"
        )
    return ev
