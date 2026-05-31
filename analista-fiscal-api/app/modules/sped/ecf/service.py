"""Service — SPED ECF Lucro Presumido (Sprint 16 PR2).

Orquestra:

1. Valida elegibilidade (apenas Lucro Presumido nesta versão; Lucro Real
   e Arbitrado ficam para Fase 5).
2. Idempotência §8.9 — consulta versão ativa antes de gerar.
3. Coleta de insumos:
   * empresa (identificação 0000/0030)
   * 4 apurações IRPJ + 4 CSLL trimestrais (Sprint 11 PR1)
   * plano de contas vigente em 31/12 (SCD Type 2)
   * saldos contábeis ao fim de cada trimestre (K155)
   * ECD vinculada do mesmo ano (C040) — populada se PR1 desta sprint
     já gerou a ECD.
4. Monta ``EntradaEcf`` (DTO puro) → chama gerador puro → persiste em
   ``arquivo_sped`` (supersede da versão anterior se ``forcar``).

Princípios cravados:

* §8.2 — re-geração nunca apaga; cria nova linha com ``supersedes``.
* §8.8 — LLM não participa do gerador (pipeline 100% determinístico).
* §8.9 — idempotência cravada em DB (UNIQUE parcial) + check no service.
* §8.10 — log estruturado com hash + tamanho + total_linhas.
* §8.12 — service NÃO faz transmissão.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.plano_referencial import PLANO_REFERENCIAL
from app.modules.empresa.repo import EmpresaRepo
from app.modules.sped.ecd.repo import (
    ArquivoSpedRepo,
    ContabilParaEcdRepo,  # reusa: listar_plano_contas_vigente
)
from app.modules.sped.ecf.gerador import (
    ALGORITMO_VERSAO,
    ApuracaoTrimestralLp,
    ContaPlanoEcf,
    EcdVinculada,
    EntradaEcf,
    IdentificacaoEmpresaEcf,
    InformacoesGerais,
    SaldoContaTrimestre,
    gerar_ecf,
)
from app.modules.sped.ecf.repo import (
    ApuracaoTrimestreLp,
    ApuracoesLpParaEcfRepo,
    EcdVinculadaRepo,
    SaldosTrimestreParaEcfRepo,
    SaldoTrimestreConta,
)
from app.shared.db.models import (
    ArquivoSped,
    ContaContabil,
    Empresa,
)
from app.shared.exceptions import (
    EmpresaNaoElegivelEcd,  # reusa — MEI também é rejeitado para ECF
    EmpresaNaoEncontrada,
    SemDadosParaSped,
    SpedJaGerado,
)

log = structlog.get_logger(__name__)

_ZERO = Decimal("0")
_TIPO = "ecf"
# Mapping regime → forma de tributação (registro 0000/0010).
_REGIME_FORMA_TRIB = {
    "lucro_presumido": "4",
    # Lucro Real e híbridos ficam fora do MVP. Adicionar Q (Arbitrado) e
    # 3 (Real/Presumido) em sprint futura.
}


@dataclass(frozen=True, slots=True)
class EcfGerada:
    """Bundle devolvido ao service caller: linha persistida + bytes."""

    arquivo: ArquivoSped
    conteudo: bytes


class EcfService:
    async def gerar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        *,
        ano: int,
        forcar: bool = False,
        usuario_id: UUID | None = None,
    ) -> EcfGerada:
        """Gera (ou recupera) a ECF anual da empresa.

        Raises:
            EmpresaNaoEncontrada: ID inexistente ou inativa.
            EmpresaNaoElegivelEcd: MEI (LC 123 art. 18-A §13 — dispensa)
                ou regime não-LP (Lucro Real / Arbitrado fora do MVP).
            SpedJaGerado: já existe arquivo ativo e ``forcar=False``.
            SemDadosParaSped: faltam apurações trimestrais (IRPJ ou CSLL)
                ou plano de contas vazio.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if empresa.regime_tributario == "mei":
            raise EmpresaNaoElegivelEcd(
                "MEI dispensado de ECF (LC 123/2006 art. 18-A §13)."
            )
        if empresa.regime_tributario not in _REGIME_FORMA_TRIB:
            raise EmpresaNaoElegivelEcd(
                f"ECF para regime {empresa.regime_tributario!r} ainda não "
                "suportada nesta versão (MVP: apenas Lucro Presumido)."
            )

        periodo_inicio = date(ano, 1, 1)
        periodo_fim = date(ano, 12, 31)

        sped_repo = ArquivoSpedRepo(session)
        ativo = await sped_repo.ativo(
            empresa_id, _TIPO, periodo_inicio, periodo_fim,
        )
        if ativo is not None and not forcar:
            raise SpedJaGerado(
                f"ECF {ano} já gerada (id={ativo.id}). "
                "Use ``forcar=true`` para criar nova versão."
            )

        # Apurações trimestrais — núcleo do bloco P.
        apuracoes = await ApuracoesLpParaEcfRepo(session).listar_trimestres_do_ano(
            empresa_id, ano,
        )
        if not apuracoes:
            raise SemDadosParaSped(
                f"Nenhuma apuração IRPJ/CSLL trimestral encontrada para {ano}. "
                "Apure os 4 trimestres antes de gerar a ECF."
            )

        # Plano de contas vigente em 31/12.
        plano = await ContabilParaEcdRepo(session).listar_plano_contas_vigente(
            empresa_id, periodo_fim,
        )
        if not plano:
            raise SemDadosParaSped(
                f"Plano de contas vazio para empresa em {periodo_fim}."
            )

        # Saldos contábeis ao fim de cada trimestre.
        saldos_repo = SaldosTrimestreParaEcfRepo(session)
        saldos_por_trimestre: list[
            tuple[int, tuple[SaldoContaTrimestre, ...]]
        ] = []
        for ap in apuracoes:
            saldos_db = await saldos_repo.saldos_no_trimestre(
                empresa_id, ano, ap.numero,
            )
            saldos_por_trimestre.append(
                (ap.numero, tuple(_converter_saldo(s) for s in saldos_db))
            )

        # ECD vinculada.
        ecd = await EcdVinculadaRepo(session).por_ano(empresa_id, ano)
        ecd_vinc = (
            EcdVinculada(
                hash_ecd=ecd.hash_arquivo,
                num_recibo_ecd=ecd.recibo_transmissao,
                data_recibo=(
                    ecd.transmitido_em.date() if ecd.transmitido_em else None
                ),
            )
            if ecd is not None
            else None
        )

        entrada = _montar_entrada_ecf(
            empresa=empresa,
            ano=ano,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            plano=plano,
            apuracoes=apuracoes,
            saldos_por_trimestre=saldos_por_trimestre,
            ecd_vinculada=ecd_vinc,
        )
        gerado = gerar_ecf(entrada)

        arquivo = ArquivoSped(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=_TIPO,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            conteudo_bytea=gerado.conteudo,
            tamanho_bytes=gerado.tamanho_bytes,
            hash_arquivo=gerado.hash_sha256,
            status="gerado",
            algoritmo_versao=ALGORITMO_VERSAO,
            gerado_por_usuario_id=usuario_id,
            supersedes=ativo.id if ativo else None,
        )
        await sped_repo.criar(arquivo)
        if ativo is not None:
            await sped_repo.marcar_superseded(ativo, arquivo.id)

        await session.commit()
        await session.refresh(arquivo)

        log.info(
            "sped.ecf.gerado",
            empresa_id=str(empresa_id),
            ano=ano,
            tamanho_bytes=gerado.tamanho_bytes,
            total_linhas=gerado.total_linhas,
            hash=gerado.hash_sha256,
            ecd_vinculada=str(ecd.id) if ecd else None,
            superseded=str(ativo.id) if ativo else None,
            algoritmo_versao=ALGORITMO_VERSAO,
        )
        return EcfGerada(arquivo=arquivo, conteudo=gerado.conteudo)


# ── Helpers de montagem ─────────────────────────────────────────────────────


def _montar_entrada_ecf(
    *,
    empresa: Empresa,
    ano: int,
    periodo_inicio: date,
    periodo_fim: date,
    plano: list[ContaContabil],
    apuracoes: list[ApuracaoTrimestreLp],
    saldos_por_trimestre: list[tuple[int, tuple[SaldoContaTrimestre, ...]]],
    ecd_vinculada: EcdVinculada | None,
) -> EntradaEcf:
    if not empresa.codigo_municipio_ibge:
        raise SemDadosParaSped(
            "Empresa sem codigo_municipio_ibge — execute PATCH "
            "/v1/empresas/{id}/municipio-ibge antes de gerar a ECF."
        )
    ident = IdentificacaoEmpresaEcf(
        cnpj=empresa.cnpj,
        razao_social=empresa.razao_social,
        nome_fantasia=empresa.nome_fantasia,
        uf=empresa.uf or "",
        municipio=empresa.municipio,
        codigo_municipio_ibge=empresa.codigo_municipio_ibge,
        inscricao_estadual=empresa.ie,
        inscricao_municipal=empresa.im,
    )

    plano_dto = [
        ContaPlanoEcf(
            codigo=c.codigo,
            descricao=c.descricao,
            natureza=c.natureza,
            nivel=c.nivel,
            tipo_conta="A" if c.aceita_lancamento else "S",
            codigo_pai=_codigo_pai_do_codigo(c.codigo, plano),
            codigo_ecd_referencial=c.codigo_ecd_referencial
            or _codigo_ecd_do_plano_referencial(c.codigo),
        )
        for c in plano
    ]

    apuracoes_dto = tuple(_converter_apuracao(ap) for ap in apuracoes)

    # Y540 — discriminação de receita por atividade. MVP: 1 entrada por
    # trimestre agregada (já temos só 1 atividade preponderante no MVP).
    receita_total_anual = sum(
        (ap.irpj.receita_bruta_trimestre or _ZERO for ap in apuracoes),
        _ZERO,
    )
    discriminacao = (
        (("01", receita_total_anual),) if receita_total_anual > _ZERO else ()
    )
    info = InformacoesGerais(
        discriminacao_receita=discriminacao,
        socios=(),  # Sócios entram em sprint futura — exige join com modulo socio
    )

    return EntradaEcf(
        empresa=ident,
        ano_calendario=ano,
        inicio_exercicio=periodo_inicio,
        fim_exercicio=periodo_fim,
        forma_tributacao=_REGIME_FORMA_TRIB[empresa.regime_tributario],
        ecd_vinculada=ecd_vinculada,
        plano_contas=tuple(plano_dto),
        saldos_por_trimestre=tuple(saldos_por_trimestre),
        apuracoes_trimestrais=apuracoes_dto,
        informacoes_gerais=info,
    )


def _converter_apuracao(ap: ApuracaoTrimestreLp) -> ApuracaoTrimestralLp:
    """Mapeia (IrpjLpSnapshot + CsllLpSnapshot) → ApuracaoTrimestralLp."""
    irpj = ap.irpj
    csll = ap.csll
    inicio, fim = _datas_do_trimestre(ap.competencia)
    return ApuracaoTrimestralLp(
        inicio=inicio,
        fim=fim,
        numero_trimestre=ap.numero,
        receita_bruta=irpj.receita_bruta_trimestre or _ZERO,
        percentual_presuncao_irpj=irpj.percentual_presuncao or _ZERO,
        percentual_presuncao_csll=csll.percentual_presuncao or _ZERO,
        base_presumida_irpj=irpj.base_presumida or _ZERO,
        base_presumida_csll=csll.base_presumida or _ZERO,
        ganhos_capital=irpj.ganhos_capital or _ZERO,
        receitas_aplicacoes=irpj.receitas_aplicacoes or _ZERO,
        outras_adicoes_irpj=irpj.outras_adicoes or _ZERO,
        outras_adicoes_csll=csll.outras_adicoes or _ZERO,
        base_total_irpj=irpj.base_total or _ZERO,
        base_total_csll=csll.base_total or _ZERO,
        limite_adicional_irpj=irpj.limite_adicional or _ZERO,
        irpj_normal=irpj.irpj_normal or _ZERO,
        irpj_adicional=irpj.irpj_adicional or _ZERO,
        irpj_total=irpj.irpj_total,
        irrf_a_compensar=irpj.irrf_a_compensar or _ZERO,
        irrf_consumido=irpj.irrf_consumido or _ZERO,
        irpj_devido=irpj.irpj_devido if irpj.irpj_devido is not None else irpj.irpj_total,
        csll_devida=csll.csll,
    )


def _converter_saldo(s: SaldoTrimestreConta) -> SaldoContaTrimestre:
    return SaldoContaTrimestre(
        codigo_conta=s.conta.codigo,
        saldo_inicial=abs(s.saldo_inicial),
        indicador_saldo_inicial=_dc_indicador(s.saldo_inicial, s.conta.natureza),
        debitos=s.debitos_acumulados,
        creditos=s.creditos_acumulados,
        saldo_final=abs(s.saldo_final),
        indicador_saldo_final=_dc_indicador(s.saldo_final, s.conta.natureza),
    )


def _datas_do_trimestre(competencia: date) -> tuple[date, date]:
    """01-jan → (01-jan, 31-mar) etc."""
    from datetime import timedelta

    inicio = date(competencia.year, competencia.month, 1)
    mes_fim = competencia.month + 2
    if mes_fim == 12:
        fim = date(competencia.year, 12, 31)
    else:
        prox = date(competencia.year, mes_fim + 1, 1)
        fim = prox - timedelta(days=1)
    return inicio, fim


def _dc_indicador(valor: Decimal, natureza_conta: str) -> str:
    if valor >= _ZERO:
        return natureza_conta
    return "C" if natureza_conta == "D" else "D"


def _codigo_pai_do_codigo(
    codigo: str, todos: list[ContaContabil]
) -> str | None:
    if "." not in codigo:
        return None
    codigos_existentes = {c.codigo for c in todos}
    partes = codigo.split(".")
    for fim in range(len(partes) - 1, 0, -1):
        candidato = ".".join(partes[:fim])
        if candidato in codigos_existentes:
            return candidato
    return None


def _codigo_ecd_do_plano_referencial(codigo: str) -> str | None:
    for item in PLANO_REFERENCIAL:
        if item.codigo == codigo:
            return item.codigo_ecd_referencial
    return None
