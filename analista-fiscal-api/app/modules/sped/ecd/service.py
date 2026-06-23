"""Service — SPED ECD (Sprint 16 PR1).

Orquestra:

1. Validação de elegibilidade (MEI rejeitado).
2. Idempotência (§8.9): consulta versão ativa antes de gerar.
3. Coleta de insumos: empresa + plano de contas + lançamentos + saldos
   mensais + balanço + DRE (este último reusa `relatorios.calcula_*`).
4. Montagem da ``EntradaEcd`` (DTO puro).
5. Chamada do gerador puro → ``ArquivoEcdGerado`` (bytes + hash).
6. Persistência em ``arquivo_sped`` (supersede da versão anterior se ``forcar``).

Princípios cravados:

* §8.2 — re-geração nunca apaga; cria nova linha com ``supersedes``.
* §8.9 — UNIQUE parcial no DB + check no service.
* §8.10 — log estruturado em cada geração com hash + tamanho.
* §8.12 — service NÃO faz transmissão; apenas gera e devolve.
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
from app.modules.relatorios.calcula_balanco import (
    ResultadoBalanco,
    calcular_balanco,
)
from app.modules.relatorios.calcula_dre import (
    ResultadoDre,
    calcular_dre,
)
from app.modules.relatorios.calcula_dre import (
    SaldoConta as SaldoDre,
)
from app.modules.relatorios.repo import SaldosPeriodoRepo
from app.modules.sped.ecd.gerador import (
    ALGORITMO_VERSAO,
    ContaPlano,
    EntradaEcd,
    IdentificacaoEmpresaEcd,
    LancamentoEcd,
    LinhaDemonstracao,
    PartidaLanc,
    SaldoPeriodico,
    SaldoPeriodicoConta,
    SaldoResultadoConta,
    gerar_ecd,
)
from app.modules.sped.ecd.repo import (
    ArquivoSpedRepo,
    ContabilParaEcdRepo,
    LancamentoComPartidas,
    SaldoMensalConta,
)
from app.shared.db.models import ArquivoSped, ContaContabil, Empresa
from app.shared.exceptions import (
    EmpresaNaoElegivelEcd,
    EmpresaNaoEncontrada,
    SemDadosParaSped,
    SpedJaGerado,
)

log = structlog.get_logger(__name__)

_ZERO = Decimal("0")
_TIPO = "ecd"


@dataclass(frozen=True, slots=True)
class EcdGerada:
    """Bundle devolvido ao service caller: linha persistida + bytes."""

    arquivo: ArquivoSped
    conteudo: bytes


class EcdService:
    async def gerar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        *,
        ano: int,
        forcar: bool = False,
        usuario_id: UUID | None = None,
    ) -> EcdGerada:
        """Gera (ou recupera) a ECD anual da empresa.

        Raises:
            EmpresaNaoEncontrada: empresa inativa ou ID inexistente.
            EmpresaNaoElegivelEcd: empresa MEI.
            SpedJaGerado: arquivo ativo existe e ``forcar=False``.
            SemDadosParaSped: plano vazio OU sem lançamentos no ano.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if empresa.regime_tributario == "mei":
            raise EmpresaNaoElegivelEcd(
                "MEI dispensado de ECD (LC 123/2006 art. 18-A §13)."
            )

        periodo_inicio = date(ano, 1, 1)
        periodo_fim = date(ano, 12, 31)

        sped_repo = ArquivoSpedRepo(session)
        ativo = await sped_repo.ativo(
            empresa_id, _TIPO, periodo_inicio, periodo_fim,
        )
        if ativo is not None and not forcar:
            raise SpedJaGerado(
                f"ECD {ano} já gerada (id={ativo.id}). "
                "Use ``forcar=true`` para criar nova versão."
            )

        contabil = ContabilParaEcdRepo(session)
        plano = await contabil.listar_plano_contas_vigente(
            empresa_id, periodo_fim
        )
        if not plano:
            raise SemDadosParaSped(
                f"Plano de contas vazio para empresa em {periodo_fim}."
            )
        lancs = await contabil.listar_lancamentos_do_periodo(
            empresa_id, periodo_inicio, periodo_fim
        )
        if not lancs:
            raise SemDadosParaSped(
                f"Nenhum lançamento contábil confirmado em {ano}."
            )
        saldos_mensais = await contabil.listar_saldos_mensais(
            empresa_id, periodo_inicio, periodo_fim
        )

        # Balanço (snapshot em 31/12) + DRE (período inteiro).
        saldos_repo = SaldosPeriodoRepo(session)
        saldos_posicao = await saldos_repo.saldos_posicao_em(
            empresa_id, periodo_fim
        )
        balanco_resultado = calcular_balanco(saldos_posicao)
        movimento_resultado = await saldos_repo.movimento_resultado_periodo(
            empresa_id, periodo_inicio, periodo_fim
        )
        irpj_csll = await saldos_repo.irpj_csll_apurado_no_periodo(
            empresa_id, periodo_inicio, periodo_fim
        )
        dre_resultado = calcular_dre(
            movimento_resultado, irpj_csll_apurado=irpj_csll
        )

        entrada = _montar_entrada_ecd(
            empresa=empresa,
            ano=ano,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            plano=plano,
            lancamentos=lancs,
            saldos_mensais=saldos_mensais,
            saldos_resultado=movimento_resultado,
            balanco_linhas=_balanco_para_linhas(balanco_resultado),
            dre_linhas=_dre_para_linhas(dre_resultado),
        )
        gerado = gerar_ecd(entrada)

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
            "sped.ecd.gerado",
            empresa_id=str(empresa_id),
            ano=ano,
            tamanho_bytes=gerado.tamanho_bytes,
            total_linhas=gerado.total_linhas,
            hash=gerado.hash_sha256,
            superseded=str(ativo.id) if ativo else None,
            algoritmo_versao=ALGORITMO_VERSAO,
        )
        return EcdGerada(arquivo=arquivo, conteudo=gerado.conteudo)


# ── Helpers de montagem ──────────────────────────────────────────────────────


def _montar_entrada_ecd(
    *,
    empresa: Empresa,
    ano: int,
    periodo_inicio: date,
    periodo_fim: date,
    plano: list[ContaContabil],
    lancamentos: list[LancamentoComPartidas],
    saldos_mensais: list[SaldoMensalConta],
    saldos_resultado: list[SaldoDre],
    balanco_linhas: list[LinhaDemonstracao],
    dre_linhas: list[LinhaDemonstracao],
) -> EntradaEcd:
    # Identificação.
    if not empresa.codigo_municipio_ibge:
        raise SemDadosParaSped(
            "Empresa sem codigo_municipio_ibge — execute PATCH "
            "/v1/empresas/{id}/municipio-ibge antes de gerar a ECD."
        )
    ident = IdentificacaoEmpresaEcd(
        cnpj=empresa.cnpj,
        razao_social=empresa.razao_social,
        nome_fantasia=empresa.nome_fantasia,
        uf=empresa.uf or "",
        municipio=empresa.municipio,
        codigo_municipio_ibge=empresa.codigo_municipio_ibge,
        inscricao_estadual=empresa.ie,
        inscricao_municipal=empresa.im,
    )

    # Plano de contas — tipo sintético/analítico vem de `aceita_lancamento`.
    plano_dto = [
        ContaPlano(
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

    # Saldos mensais agrupados por competência (intervalo do I150 = mês civil).
    sp_lista = _saldos_para_periodicos(saldos_mensais)

    # Lançamentos.
    lanc_dtos: list[LancamentoEcd] = []
    for numero_seq, cp in enumerate(lancamentos, start=1):
        partidas = tuple(
            PartidaLanc(
                codigo_conta=conta.codigo,
                valor=partida.valor,
                indicador_dc=partida.tipo,
                historico=cp.lancamento.historico,
            )
            for partida, conta in cp.partidas
        )
        lanc_dtos.append(
            LancamentoEcd(
                numero=str(numero_seq),
                data=cp.lancamento.data_lancamento,
                valor_total=cp.lancamento.total_debito,
                indicador_origem="N",
                partidas=partidas,
            )
        )

    # Saldo de resultado antes do encerramento (I355).
    res_dtos = tuple(
        SaldoResultadoConta(
            codigo_conta=s.codigo,
            valor=abs(s.saldo_final),
            indicador_dc=_dc_para_resultado(s),
        )
        for s in saldos_resultado
        if s.saldo_final != _ZERO
    )

    return EntradaEcd(
        empresa=ident,
        ano_calendario=ano,
        inicio_exercicio=periodo_inicio,
        fim_exercicio=periodo_fim,
        plano_contas=tuple(plano_dto),
        saldos_periodicos=tuple(sp_lista),
        lancamentos=tuple(lanc_dtos),
        saldos_resultado_antes_encerramento=res_dtos,
        balanco=tuple(balanco_linhas),
        dre=tuple(dre_linhas),
    )


def _codigo_pai_do_codigo(
    codigo: str, todos: list[ContaContabil]
) -> str | None:
    """Heurística: pai é a sub-conta pontuada anterior se existir no plano.

    Ex.: ``1.1.1.01`` → tenta ``1.1.1``; cai para ``1.1`` → ``1``. Retorna
    ``None`` se a conta é raiz (nível 1) ou se nenhum prefixo casa.
    """
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
    """Fallback ao plano referencial RFB embutido se a conta da empresa
    não tem ``codigo_ecd_referencial`` populado (planos antigos).
    """
    for item in PLANO_REFERENCIAL:
        if item.codigo == codigo:
            return item.codigo_ecd_referencial
    return None


def _saldos_para_periodicos(
    saldos: list[SaldoMensalConta],
) -> list[SaldoPeriodico]:
    """Agrupa saldos por competência (mês) → 1 ``SaldoPeriodico`` por mês.

    Para o intervalo do I150 usamos o 1º dia da competência como início e
    o 1º dia do mês seguinte − 1 dia como fim. Saldos zero (sem movimento)
    são omitidos para reduzir tamanho do arquivo.
    """
    from collections import defaultdict
    from datetime import timedelta

    por_mes: dict[date, list[SaldoMensalConta]] = defaultdict(list)
    for s in saldos:
        if (
            s.saldo_inicial == _ZERO
            and s.total_debitos == _ZERO
            and s.total_creditos == _ZERO
            and s.saldo_final == _ZERO
        ):
            continue
        por_mes[s.competencia].append(s)

    periodicos: list[SaldoPeriodico] = []
    for competencia in sorted(por_mes):
        # competencia armazenada como 1º dia do mês.
        inicio = competencia
        # Último dia do mês = 1º do mês seguinte − 1 dia.
        if competencia.month == 12:
            prox = date(competencia.year + 1, 1, 1)
        else:
            prox = date(competencia.year, competencia.month + 1, 1)
        fim = prox - timedelta(days=1)
        linhas = tuple(
            SaldoPeriodicoConta(
                codigo_conta=s.conta.codigo,
                saldo_inicial=abs(s.saldo_inicial),
                indicador_saldo_inicial=_dc_indicador(
                    s.saldo_inicial, s.conta.natureza
                ),
                total_debitos=s.total_debitos,
                total_creditos=s.total_creditos,
                saldo_final=abs(s.saldo_final),
                indicador_saldo_final=_dc_indicador(
                    s.saldo_final, s.conta.natureza
                ),
            )
            for s in por_mes[competencia]
        )
        periodicos.append(
            SaldoPeriodico(inicio=inicio, fim=fim, saldos=linhas)
        )
    return periodicos


def _dc_indicador(valor: Decimal, natureza_conta: str) -> str:
    """Decide indicador D/C do saldo no formato ECD.

    Por convenção interna, ``saldo_conta_mes.saldo_*`` é signed: positivo
    significa saldo NA natureza padrão da conta; negativo significa saldo
    INVERTIDO (ex.: caixa negativo = conta credora momentânea). O leiaute
    ECD pede o indicador D/C — convertemos:
    """
    if valor >= _ZERO:
        return natureza_conta
    return "C" if natureza_conta == "D" else "D"


def _dc_para_resultado(s: SaldoDre) -> str:
    """Receitas positivas → C; despesas positivas → D.

    O ``SaldoConta`` do DRE chega com ``saldo_final`` SEMPRE positivo na
    natureza padrão da conta. Códigos 4.x são receita (C); 5.x são
    despesa (D).
    """
    return "C" if s.codigo.startswith("4") else "D"


def _balanco_para_linhas(resultado: ResultadoBalanco) -> list[LinhaDemonstracao]:
    """Converte ``ResultadoBalanco`` em linhas do J100.

    Cada agrupamento (Ativo Circulante, Ativo Não Circ., Passivo Circ., …)
    vira uma linha com ``codigo_aglutinacao`` igual ao código de prefixo
    do plano referencial RFB (``1.01``, ``1.02``, ``2.01``, ``2.02``, ``2.03``)
    + uma linha de total geral.
    """
    return [
        LinhaDemonstracao(
            codigo_aglutinacao="1.01",
            nivel=2,
            natureza="D",
            descricao=resultado.ativo_circulante.rotulo,
            valor=resultado.ativo_circulante.valor,
        ),
        LinhaDemonstracao(
            codigo_aglutinacao="1.02",
            nivel=2,
            natureza="D",
            descricao=resultado.ativo_nao_circulante.rotulo,
            valor=resultado.ativo_nao_circulante.valor,
        ),
        LinhaDemonstracao(
            codigo_aglutinacao="1",
            nivel=1,
            natureza="D",
            descricao=resultado.ativo_total.rotulo,
            valor=resultado.ativo_total.valor,
        ),
        LinhaDemonstracao(
            codigo_aglutinacao="2.01",
            nivel=2,
            natureza="C",
            descricao=resultado.passivo_circulante.rotulo,
            valor=resultado.passivo_circulante.valor,
        ),
        LinhaDemonstracao(
            codigo_aglutinacao="2.02",
            nivel=2,
            natureza="C",
            descricao=resultado.passivo_nao_circulante.rotulo,
            valor=resultado.passivo_nao_circulante.valor,
        ),
        LinhaDemonstracao(
            codigo_aglutinacao="2.03",
            nivel=2,
            natureza="C",
            descricao=resultado.patrimonio_liquido.rotulo,
            valor=resultado.patrimonio_liquido.valor,
        ),
        LinhaDemonstracao(
            codigo_aglutinacao="2",
            nivel=1,
            natureza="C",
            descricao=resultado.passivo_mais_pl_total.rotulo,
            valor=resultado.passivo_mais_pl_total.valor,
        ),
    ]


def _dre_para_linhas(resultado: ResultadoDre) -> list[LinhaDemonstracao]:
    """Converte ``ResultadoDre`` em linhas do J150.

    Mapping para ``codigo_aglutinacao`` segue o plano referencial RFB:

    * ``3.01`` Receita Bruta (C)
    * ``3.02`` Deduções (D)
    * ``3.03`` Receita Líquida (C)
    * ``3.04`` CMV/CSV (D)
    * ``3.05`` Lucro Bruto (C)
    * ``3.06`` Despesas com Pessoal (D)
    * ``3.07`` Outras Despesas (D)
    * ``3.08`` EBITDA (C)
    * ``3.09`` Depreciação (D)
    * ``3.10`` EBIT (C)
    * ``3.11`` Resultado Financeiro (C/D)
    * ``3.12`` LAIR (C)
    * ``3.13`` IRPJ + CSLL (D)
    * ``3.14`` Lucro Líquido (C)
    """
    return [
        LinhaDemonstracao("3.01", 2, "C", resultado.receita_bruta.rotulo, resultado.receita_bruta.valor),
        LinhaDemonstracao("3.02", 2, "D", resultado.deducoes.rotulo, resultado.deducoes.valor),
        LinhaDemonstracao("3.03", 2, "C", resultado.receita_liquida.rotulo, resultado.receita_liquida.valor),
        LinhaDemonstracao("3.04", 2, "D", resultado.cmv.rotulo, resultado.cmv.valor),
        LinhaDemonstracao("3.05", 2, "C", resultado.lucro_bruto.rotulo, resultado.lucro_bruto.valor),
        LinhaDemonstracao("3.06", 2, "D", resultado.despesas_pessoal.rotulo, resultado.despesas_pessoal.valor),
        LinhaDemonstracao("3.07", 2, "D", resultado.outras_despesas.rotulo, resultado.outras_despesas.valor),
        LinhaDemonstracao("3.08", 2, "C", resultado.ebitda.rotulo, resultado.ebitda.valor),
        LinhaDemonstracao("3.09", 2, "D", resultado.depreciacao.rotulo, resultado.depreciacao.valor),
        LinhaDemonstracao("3.10", 2, "C", resultado.ebit.rotulo, resultado.ebit.valor),
        LinhaDemonstracao(
            "3.11",
            2,
            "C" if resultado.resultado_financeiro.valor >= _ZERO else "D",
            resultado.resultado_financeiro.rotulo,
            abs(resultado.resultado_financeiro.valor),
        ),
        LinhaDemonstracao("3.12", 2, "C", resultado.lair.rotulo, resultado.lair.valor),
        LinhaDemonstracao("3.13", 2, "D", resultado.irpj_csll.rotulo, resultado.irpj_csll.valor),
        LinhaDemonstracao("3.14", 1, "C", resultado.lucro_liquido.rotulo, resultado.lucro_liquido.valor),
    ]
