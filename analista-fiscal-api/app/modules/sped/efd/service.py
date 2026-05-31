"""Service — EFD-Contribuições mensal (Sprint 17 PR1).

Orquestra:

1. Validação de elegibilidade (MEI e Simples Nacional rejeitados).
2. Idempotência (§8.9): consulta versão ativa antes de gerar.
3. Coleta de insumos: empresa + documentos do mês + apuração PIS/Cofins.
4. Montagem da ``EntradaEfdContribuicoes`` (DTO puro).
5. Chamada do gerador puro → ``ArquivoEfdContribuicoesGerado`` (bytes + hash).
6. Persistência em ``arquivo_sped`` (supersede da versão anterior se ``forcar``).

Princípios cravados:

* §8.2 — re-geração nunca apaga; cria nova linha com ``supersedes``.
* §8.9 — UNIQUE parcial no DB + check no service.
* §8.10 — log estruturado em cada geração com hash + tamanho.
* §8.12 — service NÃO faz transmissão; apenas gera e devolve.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.icms.repo import AliquotaIcmsRepo
from app.modules.imobilizado.repo import BemImobilizadoRepo
from app.modules.sped.efd.ciap import (
    BemCiap,
    SnapshotCiap,
    calcular_apropriacao_ciap,
)
from app.modules.sped.efd.gerador_contribuicoes import (
    ALGORITMO_VERSAO,
    ApuracaoMensalPisCofins,
    DocumentoMercadoriaEfd,
    DocumentoServicoEfd,
    EntradaEfdContribuicoes,
    IdentificacaoEmpresaEfd,
    ParticipanteEfd,
    gerar_efd_contribuicoes,
)
from app.modules.sped.efd.gerador_icms_ipi import (
    ALGORITMO_VERSAO as ALGORITMO_VERSAO_ICMS,
)
from app.modules.sped.efd.gerador_icms_ipi import (
    ApuracaoMensalIcms,
    ApuracaoMensalIpi,
    DocumentoIcmsEfd,
    EntradaEfdIcmsIpi,
    IdentificacaoEmpresaEfdIcms,
    ObrigacaoIcmsRecolher,
    ParticipanteIcms,
    gerar_efd_icms_ipi,
)
from app.modules.sped.efd.repo import (
    ApuracaoIcmsLida,
    ApuracaoPisCofinsAgregada,
    ApuracoesIcmsRepo,
    ApuracoesPisCofinsRepo,
    ArquivoSpedRepo,
    DocumentosParaEfdRepo,
)
from app.shared.db.models import (
    ArquivoSped,
    BemImobilizado,
    DocumentoFiscal,
    Empresa,
)
from app.shared.exceptions import (
    EmpresaNaoElegivelEfd,
    EmpresaNaoEncontrada,
    SemDadosParaSped,
    SpedJaGerado,
)

log = structlog.get_logger(__name__)

_ZERO = Decimal("0")
_CEM = Decimal("100")
_TIPO = "efd_contribuicoes"
_TIPO_ICMS_IPI = "efd_icms_ipi"
_REGIMES_ELEGIVEIS = frozenset({"lucro_presumido", "lucro_real"})
# Vencimento padrão fallback do ICMS — 10º dia do mês seguinte
# (Convênio ICMS 92/2006). Sprint 19.6 PR1 (#33) introduziu lookup
# real por UF via ``AliquotaIcmsRepo.dia_vencimento_padrao_por_uf``;
# este valor só é usado quando a UF não tem vigência cadastrada
# (improvável após seed da migration 0046).
_DIA_VENCIMENTO_ICMS_FALLBACK = 10


@dataclass(frozen=True, slots=True)
class EfdContribuicoesGerada:
    """Bundle devolvido ao caller: linha persistida + bytes do .txt."""

    arquivo: ArquivoSped
    conteudo: bytes


class EfdContribuicoesService:
    async def gerar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        *,
        competencia: date,
        forcar: bool = False,
        usuario_id: UUID | None = None,
    ) -> EfdContribuicoesGerada:
        """Gera (ou recupera) a EFD-Contribuições do mês.

        ``competencia`` deve ser o primeiro dia do mês — o service deriva
        ``periodo_inicio`` e ``periodo_fim`` (último dia do mês).

        Raises:
            EmpresaNaoEncontrada: ID inexistente.
            EmpresaNaoElegivelEfd: MEI / Simples Nacional.
            SpedJaGerado: já existe versão ativa e ``forcar=False``.
            SemDadosParaSped: apuração PIS/Cofins ainda não calculada.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if empresa.regime_tributario not in _REGIMES_ELEGIVEIS:
            raise EmpresaNaoElegivelEfd(
                "EFD-Contribuições é obrigatória apenas para Lucro Presumido / "
                "Lucro Real (IN RFB 1.252/2012). MEI e Simples Nacional "
                "ficam dispensados — para SN, a contrapartida é a DEFIS anual."
            )

        periodo_inicio = date(competencia.year, competencia.month, 1)
        _, ultimo_dia = monthrange(competencia.year, competencia.month)
        periodo_fim = date(competencia.year, competencia.month, ultimo_dia)

        sped_repo = ArquivoSpedRepo(session)
        ativo = await sped_repo.ativo(
            empresa_id, _TIPO, periodo_inicio, periodo_fim,
        )
        if ativo is not None and not forcar:
            raise SpedJaGerado(
                f"EFD-Contribuições {competencia:%Y-%m} já gerada "
                f"(id={ativo.id}). Use ``forcar=true`` para criar nova versão."
            )

        apuracao = await ApuracoesPisCofinsRepo(session).por_competencia(
            empresa_id, periodo_inicio
        )
        if apuracao is None:
            raise SemDadosParaSped(
                f"Apuração PIS+Cofins de {competencia:%Y-%m} não encontrada. "
                "Calcule PIS e Cofins do mês antes de gerar a EFD-Contribuições."
            )

        documentos = await DocumentosParaEfdRepo(session).por_periodo(
            empresa_id, periodo_inicio, periodo_fim
        )

        entrada = _montar_entrada(
            empresa=empresa,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            apuracao=apuracao,
            documentos=documentos,
        )
        gerado = gerar_efd_contribuicoes(entrada)

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
            "sped.efd_contribuicoes.gerado",
            empresa_id=str(empresa_id),
            competencia=periodo_inicio.isoformat(),
            tamanho_bytes=gerado.tamanho_bytes,
            total_linhas=gerado.total_linhas,
            n_servicos=len(entrada.servicos),
            n_mercadorias=len(entrada.mercadorias),
            hash=gerado.hash_sha256,
            superseded=str(ativo.id) if ativo else None,
            algoritmo_versao=ALGORITMO_VERSAO,
        )
        return EfdContribuicoesGerada(arquivo=arquivo, conteudo=gerado.conteudo)


# ── Helpers de montagem ──────────────────────────────────────────────────────


def _montar_entrada(
    *,
    empresa: Empresa,
    periodo_inicio: date,
    periodo_fim: date,
    apuracao: ApuracaoPisCofinsAgregada,
    documentos: list[DocumentoFiscal],
) -> EntradaEfdContribuicoes:
    if not empresa.codigo_municipio_ibge:
        raise SemDadosParaSped(
            "Empresa sem ``codigo_municipio_ibge`` — atualize o cadastro "
            "antes de gerar a EFD-Contribuições."
        )

    ident = IdentificacaoEmpresaEfd(
        cnpj=empresa.cnpj,
        razao_social=empresa.razao_social,
        nome_fantasia=empresa.nome_fantasia,
        uf=empresa.uf or "",
        municipio=empresa.municipio,
        codigo_municipio_ibge=empresa.codigo_municipio_ibge,
        inscricao_estadual=empresa.ie,
        inscricao_municipal=empresa.im,
    )

    servicos, mercadorias, participantes = _classificar_documentos(documentos)

    apuracao_dto = ApuracaoMensalPisCofins(
        base_calculo_pis=apuracao.base_calculo_pis,
        aliquota_pis=_fracao_para_percentual(apuracao.aliquota_pis),
        valor_pis_apurado=apuracao.valor_pis,
        valor_pis_a_recolher=apuracao.valor_pis,
        base_calculo_cofins=apuracao.base_calculo_cofins,
        aliquota_cofins=_fracao_para_percentual(apuracao.aliquota_cofins),
        valor_cofins_apurado=apuracao.valor_cofins,
        valor_cofins_a_recolher=apuracao.valor_cofins,
    )

    return EntradaEfdContribuicoes(
        empresa=ident,
        competencia_inicio=periodo_inicio,
        competencia_fim=periodo_fim,
        apuracao=apuracao_dto,
        participantes=tuple(participantes),
        servicos=tuple(servicos),
        mercadorias=tuple(mercadorias),
        nome_contabilista=empresa.razao_social,
        cnpj_contabilista=empresa.cnpj,
    )


def _classificar_documentos(
    documentos: list[DocumentoFiscal],
) -> tuple[
    list[DocumentoServicoEfd],
    list[DocumentoMercadoriaEfd],
    list[ParticipanteEfd],
]:
    """Separa documentos em servico (bloco A) vs mercadoria (bloco C) e
    deriva a lista única de participantes (registro 0150).
    """
    servicos: list[DocumentoServicoEfd] = []
    mercadorias: list[DocumentoMercadoriaEfd] = []
    participantes_por_codigo: dict[str, ParticipanteEfd] = {}

    for doc in documentos:
        cod_part = _codigo_participante(doc)
        if cod_part not in participantes_por_codigo:
            participantes_por_codigo[cod_part] = ParticipanteEfd(
                codigo=cod_part,
                nome=doc.cnpj_destinatario or "PARTICIPANTE",
                cnpj=doc.cnpj_destinatario,
            )

        cancelado = doc.evento == "cancelou" or doc.status == "cancelada"
        valor_bc = doc.valor_total
        valor_pis = doc.valor_pis or _ZERO
        valor_cofins = doc.valor_cofins or _ZERO
        aliquota_pis = _aliquota_efetiva(valor_pis, valor_bc)
        aliquota_cofins = _aliquota_efetiva(valor_cofins, valor_bc)
        data_emissao = doc.emitida_em.date()
        indicador = "0" if doc.direcao == "entrada" else "1"

        if doc.tipo == "nfse":
            servicos.append(
                DocumentoServicoEfd(
                    chave=doc.chave,
                    numero=doc.numero,
                    serie=doc.serie,
                    data_emissao=data_emissao,
                    codigo_participante=cod_part,
                    valor_total=valor_bc,
                    valor_servicos=valor_bc,
                    valor_pis=valor_pis,
                    valor_cofins=valor_cofins,
                    aliquota_pis=aliquota_pis,
                    aliquota_cofins=aliquota_cofins,
                    cancelado=cancelado,
                    indicador_operacao=indicador,
                )
            )
        elif doc.tipo in {"nfe", "nfce"}:
            modelo = "55" if doc.tipo == "nfe" else "65"
            mercadorias.append(
                DocumentoMercadoriaEfd(
                    chave=doc.chave or "",
                    numero=doc.numero,
                    serie=doc.serie,
                    modelo=modelo,
                    data_emissao=data_emissao,
                    codigo_participante=cod_part,
                    valor_total=valor_bc,
                    valor_mercadorias=valor_bc,
                    valor_pis=valor_pis,
                    valor_cofins=valor_cofins,
                    aliquota_pis=aliquota_pis,
                    aliquota_cofins=aliquota_cofins,
                    cfop=doc.cfop or "5102",  # fallback: venda em UF própria
                    ncm=doc.ncm,
                    cancelado=cancelado,
                    indicador_operacao=indicador,
                    indicador_emitente="0" if doc.direcao == "saida" else "1",
                )
            )
        # cte/mdfe/nfcom/dce caem no bloco D — vazio na v1 (pendência).

    return servicos, mercadorias, list(participantes_por_codigo.values())


def _codigo_participante(doc: DocumentoFiscal) -> str:
    """Determina código único do participante (registro 0150).

    Prioridade: CNPJ do destinatário (saída) ou emitente (entrada). Se
    ausente, usa o número do doc como fallback determinístico — evita
    colidir 0150 distintos.
    """
    if doc.direcao == "saida":
        return doc.cnpj_destinatario or f"DOC-{doc.numero}"
    return doc.cnpj_emitente or f"DOC-{doc.numero}"


def _aliquota_efetiva(valor: Decimal, base: Decimal) -> Decimal:
    """Retorna alíquota % efetiva (ex.: 0,65 ou 3,00).

    Em regime cumulativo a alíquota é fixa, mas alguns docs podem ter
    base zero (cancelados ou isentos) — devolve zero para evitar divisão.
    """
    if base == _ZERO:
        return _ZERO
    return (valor / base * _CEM).quantize(Decimal("0.01"))


def _fracao_para_percentual(fracao: Decimal) -> Decimal:
    """0.0065 → 0.65 (% para a EFD).

    A apuração persistida (Sprint 11 PR1) guarda alíquota como fração
    decimal (0,65% = 0.0065). O leiaute EFD-Contribuições usa formato
    percentual (0,65). Conversão idempotente: se o valor já estiver em
    %, o resultado fica grande demais — assumimos persistido como fração.
    """
    return (fracao * _CEM).quantize(Decimal("0.01"))


# ── EFD ICMS-IPI (Sprint 17 PR2) ────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EfdIcmsIpiGerada:
    """Bundle devolvido ao caller: linha persistida + bytes do .txt."""

    arquivo: ArquivoSped
    conteudo: bytes


class EfdIcmsIpiService:
    async def gerar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        *,
        competencia: date,
        forcar: bool = False,
        usuario_id: UUID | None = None,
    ) -> EfdIcmsIpiGerada:
        """Gera (ou recupera) a EFD ICMS-IPI do mês.

        Raises:
            EmpresaNaoEncontrada: ID inexistente.
            EmpresaNaoElegivelEfd: empresa sem inscrição estadual.
            SpedJaGerado: versão ativa existe e ``forcar=False``.
            SemDadosParaSped: apuração ICMS ainda não calculada.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if not empresa.ie:
            raise EmpresaNaoElegivelEfd(
                "EFD ICMS-IPI exige inscrição estadual ativa (Ajuste SINIEF "
                "02/2009). Cadastre a IE da empresa antes de gerar o arquivo."
            )

        periodo_inicio = date(competencia.year, competencia.month, 1)
        _, ultimo_dia = monthrange(competencia.year, competencia.month)
        periodo_fim = date(competencia.year, competencia.month, ultimo_dia)

        sped_repo = ArquivoSpedRepo(session)
        ativo = await sped_repo.ativo(
            empresa_id, _TIPO_ICMS_IPI, periodo_inicio, periodo_fim,
        )
        if ativo is not None and not forcar:
            raise SpedJaGerado(
                f"EFD ICMS-IPI {competencia:%Y-%m} já gerada "
                f"(id={ativo.id}). Use ``forcar=true`` para criar nova versão."
            )

        apuracao = await ApuracoesIcmsRepo(session).por_competencia(
            empresa_id, periodo_inicio
        )
        if apuracao is None:
            raise SemDadosParaSped(
                f"Apuração ICMS de {competencia:%Y-%m} não encontrada. "
                "Calcule o ICMS do mês antes de gerar a EFD ICMS-IPI."
            )

        # EFD ICMS-IPI só carrega NF-e/NFC-e (NFS-e não tem ICMS).
        documentos = await DocumentosParaEfdRepo(session).por_periodo(
            empresa_id, periodo_inicio, periodo_fim,
            tipos=("nfe", "nfce"),
        )

        # Sprint 19.6 PR1 (#33) — vencimento ICMS por UF via SCD.
        dia_vencimento = await AliquotaIcmsRepo(session).dia_vencimento_padrao_por_uf(
            empresa.uf or apuracao.uf, periodo_inicio,
        )

        # Sprint 19.6 PR1 (#31) — CIAP. Bens com ICMS de aquisição
        # conhecido entram no bloco G. Quando lista vazia, gerador
        # devolve bloco vazio (IND_MOV='1') — comportamento atual
        # preservado para empresas sem imobilizado relevante.
        bens = await BemImobilizadoRepo(session).listar_para_ciap(
            empresa_id, periodo_fim=periodo_fim,
        )
        snapshot_ciap = _montar_ciap(bens, periodo_inicio, periodo_fim)

        entrada = _montar_entrada_icms_ipi(
            empresa=empresa,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            apuracao=apuracao,
            documentos=documentos,
            dia_vencimento=dia_vencimento,
            ciap=snapshot_ciap,
        )
        gerado = gerar_efd_icms_ipi(entrada)

        arquivo = ArquivoSped(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=_TIPO_ICMS_IPI,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            conteudo_bytea=gerado.conteudo,
            tamanho_bytes=gerado.tamanho_bytes,
            hash_arquivo=gerado.hash_sha256,
            status="gerado",
            algoritmo_versao=ALGORITMO_VERSAO_ICMS,
            gerado_por_usuario_id=usuario_id,
            supersedes=ativo.id if ativo else None,
        )
        await sped_repo.criar(arquivo)
        if ativo is not None:
            await sped_repo.marcar_superseded(ativo, arquivo.id)

        await session.commit()
        await session.refresh(arquivo)

        log.info(
            "sped.efd_icms_ipi.gerado",
            empresa_id=str(empresa_id),
            competencia=periodo_inicio.isoformat(),
            uf=empresa.uf,
            tamanho_bytes=gerado.tamanho_bytes,
            total_linhas=gerado.total_linhas,
            n_documentos=len(entrada.documentos),
            icms_a_recolher=str(apuracao.icms_a_recolher),
            hash=gerado.hash_sha256,
            superseded=str(ativo.id) if ativo else None,
            algoritmo_versao=ALGORITMO_VERSAO_ICMS,
        )
        return EfdIcmsIpiGerada(arquivo=arquivo, conteudo=gerado.conteudo)


def _montar_ciap(
    bens: list[BemImobilizado],
    periodo_inicio: date,
    periodo_fim: date,
) -> SnapshotCiap | None:
    """Sprint 19.6 PR1 (#31) — converte ``BemImobilizado`` em ``BemCiap``
    e chama a lógica pura.

    None quando não há bens elegíveis — gerador trata como bloco G
    vazio. Lista filtrada já vem pelo repo (apenas com
    ``icms_aquisicao_destacado`` preenchido).
    """
    if not bens:
        return None
    bens_ciap = [
        BemCiap(
            bem_id=str(b.id),
            descricao=b.descricao,
            data_aquisicao=b.data_aquisicao,
            # ``listar_para_ciap`` já filtra NULL — `cast` defensivo
            # para o type checker.
            icms_aquisicao_destacado=(
                b.icms_aquisicao_destacado
                if b.icms_aquisicao_destacado is not None
                else _ZERO
            ),
            data_baixa=b.data_baixa,
        )
        for b in bens
    ]
    return calcular_apropriacao_ciap(
        bens_ciap, periodo_inicio=periodo_inicio, periodo_fim=periodo_fim
    )


def _montar_entrada_icms_ipi(
    *,
    empresa: Empresa,
    periodo_inicio: date,
    periodo_fim: date,
    apuracao: ApuracaoIcmsLida,
    documentos: list[DocumentoFiscal],
    dia_vencimento: int = _DIA_VENCIMENTO_ICMS_FALLBACK,
    ciap: SnapshotCiap | None = None,
) -> EntradaEfdIcmsIpi:
    if not empresa.codigo_municipio_ibge:
        raise SemDadosParaSped(
            "Empresa sem ``codigo_municipio_ibge`` — atualize o cadastro "
            "antes de gerar a EFD ICMS-IPI."
        )
    # Pré-condição reforçada — service já barra mas DTO exige IE não-nula.
    if not empresa.ie:
        raise SemDadosParaSped(
            "Empresa sem inscrição estadual — cadastre a IE antes de gerar."
        )

    ident = IdentificacaoEmpresaEfdIcms(
        cnpj=empresa.cnpj,
        razao_social=empresa.razao_social,
        nome_fantasia=empresa.nome_fantasia,
        uf=empresa.uf or apuracao.uf,
        municipio=empresa.municipio,
        codigo_municipio_ibge=empresa.codigo_municipio_ibge,
        inscricao_estadual=empresa.ie,
        inscricao_municipal=empresa.im,
    )

    documentos_icms, participantes = _converter_documentos_icms(documentos)

    apuracao_dto = ApuracaoMensalIcms(
        valor_total_debitos=apuracao.debito,
        valor_total_creditos=apuracao.credito,
        saldo_credor_anterior=apuracao.saldo_credor_anterior,
        ajustes_devedores=apuracao.ajustes_devedores,
        ajustes_credores=apuracao.ajustes_credores,
        valor_icms_a_recolher=apuracao.icms_a_recolher,
        saldo_credor_a_transportar=apuracao.saldo_credor_a_transportar,
    )

    obrigacoes: tuple[ObrigacaoIcmsRecolher, ...] = ()
    if apuracao.icms_a_recolher > _ZERO:
        obrigacoes = (
            ObrigacaoIcmsRecolher(
                codigo_obrigacao="000",
                valor=apuracao.icms_a_recolher,
                data_vencimento=_vencimento_icms_padrao(
                    periodo_inicio, dia=dia_vencimento
                ),
            ),
        )

    return EntradaEfdIcmsIpi(
        empresa=ident,
        competencia_inicio=periodo_inicio,
        competencia_fim=periodo_fim,
        apuracao_icms=apuracao_dto,
        participantes=tuple(participantes),
        documentos=tuple(documentos_icms),
        obrigacoes_a_recolher=obrigacoes,
        ciap=ciap,
        nome_contabilista=empresa.razao_social,
        cnpj_contabilista=empresa.cnpj,
    )


def _converter_documentos_icms(
    documentos: list[DocumentoFiscal],
) -> tuple[list[DocumentoIcmsEfd], list[ParticipanteIcms]]:
    """Converte ``DocumentoFiscal`` (NF-e/NFC-e) em DTOs do gerador.

    NFS-e é filtrada upstream (não tem ICMS). CT-e/MDF-e/DCE caem no
    bloco D vazio — pendência consciente para sprint posterior.
    """
    out_docs: list[DocumentoIcmsEfd] = []
    participantes_por_codigo: dict[str, ParticipanteIcms] = {}

    for doc in documentos:
        cod_part = _codigo_participante_icms(doc)
        if cod_part not in participantes_por_codigo:
            participantes_por_codigo[cod_part] = ParticipanteIcms(
                codigo=cod_part,
                nome=doc.cnpj_destinatario or doc.cnpj_emitente or "PARTICIPANTE",
                cnpj=(
                    doc.cnpj_destinatario
                    if doc.direcao == "saida"
                    else doc.cnpj_emitente
                ),
            )

        cancelado = doc.evento == "cancelou" or doc.status == "cancelada"
        valor_bc = doc.valor_total
        valor_icms = doc.valor_icms or _ZERO
        aliquota_icms = _aliquota_efetiva_pct(valor_icms, valor_bc)
        modelo = "55" if doc.tipo == "nfe" else "65"

        out_docs.append(
            DocumentoIcmsEfd(
                chave=doc.chave or "",
                numero=doc.numero,
                serie=doc.serie,
                modelo=modelo,
                data_emissao=doc.emitida_em.date(),
                codigo_participante=cod_part,
                valor_total=valor_bc,
                valor_mercadorias=valor_bc,
                valor_icms=valor_icms,
                aliquota_icms=aliquota_icms,
                valor_ipi=doc.valor_ipi or _ZERO,
                cfop=doc.cfop or "5102",
                cst_icms=_normalizar_cst_icms(doc.cst),
                ncm=doc.ncm,
                indicador_operacao="0" if doc.direcao == "entrada" else "1",
                indicador_emitente="0" if doc.direcao == "saida" else "1",
                cancelado=cancelado,
            )
        )

    return out_docs, list(participantes_por_codigo.values())


def _codigo_participante_icms(doc: DocumentoFiscal) -> str:
    """Mesma estratégia da EFD-Contribuições — CNPJ do contraparte."""
    if doc.direcao == "saida":
        return doc.cnpj_destinatario or f"DOC-{doc.numero}"
    return doc.cnpj_emitente or f"DOC-{doc.numero}"


def _aliquota_efetiva_pct(valor: Decimal, base: Decimal) -> Decimal:
    """Alíquota % efetiva (ex.: 18,00 para 18%). Zero se base zero."""
    if base == _ZERO:
        return _ZERO
    return (valor / base * _CEM).quantize(Decimal("0.01"))


def _normalizar_cst_icms(cst: str | None) -> str:
    """``DocumentoFiscal.cst`` pode vir com 2 ou 3 dígitos.

    O leiaute EFD ICMS-IPI exige 3 dígitos (origem + CST). Quando o doc
    traz só 2, assumimos origem ``0`` (nacional) e pré-pendemos.
    """
    if not cst:
        return _DEFAULT_CST_ICMS
    if len(cst) == 3 and cst.isdigit():
        return cst
    if len(cst) == 2 and cst.isdigit():
        return f"0{cst}"
    return _DEFAULT_CST_ICMS


def _vencimento_icms_padrao(
    competencia: date, *, dia: int = _DIA_VENCIMENTO_ICMS_FALLBACK
) -> date:
    """Vencimento ICMS: ``dia``º dia do mês seguinte ao apurado.

    Sprint 19.6 PR1 (#33) — ``dia`` resolvido por UF via
    ``AliquotaIcmsRepo.dia_vencimento_padrao_por_uf``. Default
    ``_DIA_VENCIMENTO_ICMS_FALLBACK=10`` (Convênio ICMS 92/2006)
    cobre UFs sem vigência cadastrada.

    ``dia`` é validado pelo CHECK ``ck_icms_dia_vencimento_padrao``
    da migration 0046 (1..28) — vale para todos os meses incluindo
    fevereiro, sem precisar de fallback no Python.
    """
    if competencia.month == 12:
        ano = competencia.year + 1
        mes = 1
    else:
        ano = competencia.year
        mes = competencia.month + 1
    return date(ano, mes, dia)


_DEFAULT_CST_ICMS = "000"  # origem nacional + tributada integralmente
