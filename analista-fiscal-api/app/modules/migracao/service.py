"""MigracaoService — orquestra importação SPED histórico (Sprint 18 PR2).

Pipeline ECD:

1. Hash SHA-256 do bytes → ``LoteImportacaoRepo.por_hash_concluido`` (§8.9).
2. ``parse_ecd(conteudo)`` puro → ``EcdParseado``.
3. Validações cruzadas (CNPJ contra ``Empresa.cnpj`` no DB; período ≥ 2024).
4. Persiste ``arquivo_sped`` (com supersede se houver versão anterior).
5. Cria ``lote_importacao`` status='processando'.
6. Para cada lançamento parseado, monta ``LancamentoCandidato`` e chama
   ``LancadorService._persistir`` (idempotente). Contas ausentes do plano
   viram warning no ``lote.erros_jsonb`` (lançamento pulado, lote segue).
7. Marca lote ``concluido`` com ``resumo_jsonb`` cheio de métricas.

Pipeline ECF é análogo mas **snapshot-only**: parser extrai apurações
trimestrais e gravamos em ``lote.resumo_jsonb`` para audit. Não criamos
``lancamento_contabil``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, cast
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

_TZ_BR = ZoneInfo("America/Sao_Paulo")

from app.modules.contabil.lancador_auto import (
    LancamentoCandidato,
    PartidaCandidata,
)
from app.modules.contabil.lancador_service import LancadorService
from app.modules.contabil.repo import ContaContabilRepo
from app.modules.empresa.repo import EmpresaRepo
from app.modules.migracao.parser_ecd import (
    ALGORITMO_VERSAO as ALGORITMO_ECD,
    EcdInvalido,
    EcdParseado,
    LancamentoEcdParseado,
    parse_ecd,
)
from app.modules.migracao.parser_ecf import (
    ALGORITMO_VERSAO as ALGORITMO_ECF,
    EcfInvalido,
    EcfParseado,
    parse_ecf,
)
from app.modules.migracao.parser_csv import (
    ALGORITMO_VERSAO as ALGORITMO_CSV,
    BalanceteParseado,
    CsvInvalido,
    RazaoParseado,
    parse_balancete_csv,
    parse_razao_csv,
)
from app.modules.migracao.parser_efd_contribuicoes import (
    ALGORITMO_VERSAO as ALGORITMO_EFD_CONTRIB,
    DocumentoFiscalImportado,
    EfdContribuicoesInvalida,
    EfdContribuicoesParseado,
    parse_efd_contribuicoes,
)
from app.modules.migracao.parser_efd_icms_ipi import (
    ALGORITMO_VERSAO as ALGORITMO_EFD_ICMS_IPI,
    EfdIcmsIpiInvalida,
    EfdIcmsIpiParseado,
    parse_efd_icms_ipi,
)
from app.modules.migracao.repo import LoteImportacaoRepo
from app.modules.sped.ecd.repo import ArquivoSpedRepo
from app.shared.db.models import (
    ArquivoSped,
    DocumentoFiscal,
    DocumentoFiscalItem,
    LoteImportacao,
)
from app.shared.exceptions import (
    EmpresaCnpjDivergente,
    EmpresaNaoEncontrada,
    PeriodoForaCobertura,
    SpedInvalido,
)
from app.shared.types import JsonObject
from sqlalchemy import select

log = structlog.get_logger(__name__)

# Corte de período aceito pelo importador SPED histórico.
# Anterior a 2024-01-01 → ``PeriodoForaCobertura`` (vigências SCD pré-2024
# não estão seedadas e PME jovem tipicamente não precisa importar tão atrás).
PERIODO_INICIO_MINIMO = date(2024, 1, 1)

# Namespace UUID5 estável para ``origem_id`` de lançamentos importados.
_NS_MIGRACAO_LANC = uuid.UUID("5e8c1b3a-9d6f-4f12-8a45-0c9b1d2e3f40")


@dataclass(frozen=True, slots=True)
class ResultadoImportacaoEcd:
    """Resultado tipado do ``importar_sped_ecd`` para o router."""

    lote: LoteImportacao
    reaproveitado: bool  # True quando hash já tinha lote concluído (idempotência)


@dataclass(frozen=True, slots=True)
class ResultadoImportacaoEcf:
    """Resultado tipado do ``importar_sped_ecf`` para o router."""

    lote: LoteImportacao
    reaproveitado: bool


@dataclass(frozen=True, slots=True)
class ResultadoImportacaoEfd:
    """Resultado tipado dos importadores EFD (Contribuições e ICMS-IPI)."""

    lote: LoteImportacao
    reaproveitado: bool


@dataclass(frozen=True, slots=True)
class ResultadoImportacaoCsv:
    """Resultado tipado dos importadores CSV (balancete e razão)."""

    lote: LoteImportacao
    reaproveitado: bool


class MigracaoService:
    """Serviço de migração de escritório antigo — SPED ECD/ECF (PR2)."""

    def __init__(self) -> None:
        self._lancador = LancadorService()

    # ── ECD ──────────────────────────────────────────────────────────────────

    async def importar_sped_ecd(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        conteudo: bytes,
        nome_arquivo: str | None,
        usuario_id: uuid.UUID | None = None,
    ) -> ResultadoImportacaoEcd:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        # 1. Parser puro (zero I/O).
        try:
            parseado = parse_ecd(conteudo)
        except EcdInvalido as exc:
            raise SpedInvalido(f"ECD inválida: {exc}") from exc

        # 2. Validações cruzadas com o DB.
        if parseado.identificacao.cnpj != empresa.cnpj:
            raise EmpresaCnpjDivergente(
                f"CNPJ do SPED ECD ({parseado.identificacao.cnpj}) ≠ "
                f"CNPJ da empresa ({empresa.cnpj})"
            )
        if parseado.identificacao.inicio_exercicio < PERIODO_INICIO_MINIMO:
            raise PeriodoForaCobertura(
                f"Período {parseado.identificacao.inicio_exercicio} anterior ao "
                f"corte {PERIODO_INICIO_MINIMO} — importador não cobre."
            )

        lote_repo = LoteImportacaoRepo(session)

        # 3. Idempotência §8.9 — hash já importado → devolve lote anterior.
        lote_anterior = await lote_repo.por_hash_concluido(
            empresa_id, parseado.hash_arquivo
        )
        if lote_anterior is not None:
            log.info(
                "migracao.lote.reaproveitado",
                empresa_id=str(empresa_id),
                lote_id=str(lote_anterior.id),
                hash_arquivo=parseado.hash_arquivo,
            )
            return ResultadoImportacaoEcd(lote=lote_anterior, reaproveitado=True)

        # 4. Persiste ``arquivo_sped`` com supersede se houver versão anterior.
        sped_repo = ArquivoSpedRepo(session)
        anterior_arquivo = await sped_repo.ativo(
            empresa_id,
            "ecd",
            parseado.identificacao.inicio_exercicio,
            parseado.identificacao.fim_exercicio,
        )
        novo_arquivo = ArquivoSped(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="ecd",
            periodo_inicio=parseado.identificacao.inicio_exercicio,
            periodo_fim=parseado.identificacao.fim_exercicio,
            conteudo_bytea=conteudo,
            tamanho_bytes=len(conteudo),
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_ECD,
            gerado_por_usuario_id=usuario_id,
            supersedes=anterior_arquivo.id if anterior_arquivo else None,
        )
        await sped_repo.criar(novo_arquivo)
        if anterior_arquivo is not None:
            await sped_repo.marcar_superseded(anterior_arquivo, novo_arquivo.id)

        # 5. Cria lote em ``processando``.
        lote = await lote_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            fonte="sped_ecd",
            arquivo_sped_id=novo_arquivo.id,
            nome_arquivo=nome_arquivo,
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_ECD,
        )

        log.info(
            "migracao.lote.iniciado",
            empresa_id=str(empresa_id),
            lote_id=str(lote.id),
            fonte="sped_ecd",
            arquivo_sped_id=str(novo_arquivo.id),
            lancamentos_no_arquivo=len(parseado.lancamentos),
        )

        # 6. Persiste lançamentos via ``_persistir`` reusado.
        resumo, warnings = await self._persistir_lancamentos_ecd(
            session,
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            arquivo_sped_id=novo_arquivo.id,
            parseado=parseado,
        )

        # 7. Marca concluído.
        await lote_repo.concluir(
            lote.id,
            resumo=resumo,
            erros={"warnings": warnings} if warnings else None,
        )
        await session.commit()

        log.info(
            "migracao.lote.concluido",
            empresa_id=str(empresa_id),
            lote_id=str(lote.id),
            **{k: v for k, v in resumo.items() if isinstance(v, int | str)},
        )

        await session.refresh(lote)
        return ResultadoImportacaoEcd(lote=lote, reaproveitado=False)

    async def _persistir_lancamentos_ecd(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        arquivo_sped_id: uuid.UUID,
        parseado: EcdParseado,
    ) -> tuple[JsonObject, list[JsonObject]]:
        """Itera lançamentos parseados, monta candidatos, chama ``_persistir``.

        Devolve ``(resumo_jsonb, warnings)`` — warnings carregam lançamentos
        pulados por conta ausente do plano de contas da empresa.
        """
        conta_repo = ContaContabilRepo(session)
        # Cache de lookup conta_contabil por codigo (vigente na data do lançamento).
        cache_conta: dict[tuple[str, date], uuid.UUID | None] = {}

        async def conta_id_por_codigo(
            codigo: str, em: date
        ) -> uuid.UUID | None:
            chave = (codigo, em)
            if chave in cache_conta:
                return cache_conta[chave]
            conta = await conta_repo.por_codigo(empresa_id, codigo, em=em)
            cache_conta[chave] = conta.id if conta is not None else None
            return cache_conta[chave]

        criados = 0
        existentes = 0
        pulados = 0
        warnings: list[JsonObject] = []

        for lanc in parseado.lancamentos:
            partidas, conta_ausente = await self._montar_partidas(
                lanc, conta_id_por_codigo
            )
            if conta_ausente is not None:
                pulados += 1
                warnings.append(
                    {
                        "tipo": "conta_ausente",
                        "lancamento_numero": lanc.numero,
                        "codigo_conta": conta_ausente,
                        "data_lancamento": lanc.data.isoformat(),
                    }
                )
                continue

            candidato = LancamentoCandidato(
                historico=_historico_lancamento(lanc),
                data_lancamento=lanc.data,
                competencia=date(lanc.data.year, lanc.data.month, 1),
                origem_tipo="importacao",
                origem_id=_origem_id(arquivo_sped_id, lanc.numero),
                partidas=tuple(partidas),
                versao=ALGORITMO_ECD,
            )
            resultado = await self._lancador._persistir(
                session, tenant_id, empresa_id, candidato
            )
            if resultado is True:
                criados += 1
            elif resultado is False:
                existentes += 1
            else:
                # candidato.partidas vazio — não acontece neste fluxo.
                pulados += 1

        resumo: JsonObject = {
            "cnpj_arquivo": parseado.identificacao.cnpj,
            "inicio_exercicio": parseado.identificacao.inicio_exercicio.isoformat(),
            "fim_exercicio": parseado.identificacao.fim_exercicio.isoformat(),
            "contas_no_plano": len(parseado.plano_contas),
            "lancamentos_no_arquivo": len(parseado.lancamentos),
            "lancamentos_criados": criados,
            "lancamentos_existentes": existentes,
            "lancamentos_pulados": pulados,
            "saldos_periodicos": len(parseado.saldos_periodicos),
        }
        return resumo, warnings

    async def _montar_partidas(
        self,
        lanc: LancamentoEcdParseado,
        conta_id_por_codigo: object,  # callable[[str, date], Awaitable[UUID | None]]
    ) -> tuple[list[PartidaCandidata], str | None]:
        """Resolve cada partida → UUID da conta. Devolve ``(partidas, conta_ausente)``.

        Se qualquer conta não estiver no plano da empresa, devolve
        ``(partidas_parciais, codigo_ausente)`` — o caller pula o lançamento
        e registra warning.
        """
        partidas: list[PartidaCandidata] = []
        # callable typed via Protocol pra evitar Any público
        lookup = cast(_LookupCallable, conta_id_por_codigo)
        for partida in lanc.partidas:
            conta_id = await lookup(partida.codigo_conta, lanc.data)
            if conta_id is None:
                return partidas, partida.codigo_conta
            partidas.append(
                PartidaCandidata(
                    conta_id=conta_id,
                    tipo=cast(Literal["D", "C"], partida.indicador_dc),
                    valor=partida.valor,
                )
            )
        return partidas, None

    # ── ECF (snapshot read-only) ─────────────────────────────────────────────

    async def importar_sped_ecf(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        conteudo: bytes,
        nome_arquivo: str | None,
        usuario_id: uuid.UUID | None = None,
    ) -> ResultadoImportacaoEcf:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        try:
            parseado = parse_ecf(conteudo)
        except EcfInvalido as exc:
            raise SpedInvalido(f"ECF inválida: {exc}") from exc

        if parseado.identificacao.cnpj != empresa.cnpj:
            raise EmpresaCnpjDivergente(
                f"CNPJ do SPED ECF ({parseado.identificacao.cnpj}) ≠ "
                f"CNPJ da empresa ({empresa.cnpj})"
            )
        if parseado.identificacao.inicio_exercicio < PERIODO_INICIO_MINIMO:
            raise PeriodoForaCobertura(
                f"Período {parseado.identificacao.inicio_exercicio} anterior ao "
                f"corte {PERIODO_INICIO_MINIMO} — importador não cobre."
            )

        lote_repo = LoteImportacaoRepo(session)
        lote_anterior = await lote_repo.por_hash_concluido(
            empresa_id, parseado.hash_arquivo
        )
        if lote_anterior is not None:
            return ResultadoImportacaoEcf(lote=lote_anterior, reaproveitado=True)

        sped_repo = ArquivoSpedRepo(session)
        anterior_arquivo = await sped_repo.ativo(
            empresa_id,
            "ecf",
            parseado.identificacao.inicio_exercicio,
            parseado.identificacao.fim_exercicio,
        )
        novo_arquivo = ArquivoSped(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="ecf",
            periodo_inicio=parseado.identificacao.inicio_exercicio,
            periodo_fim=parseado.identificacao.fim_exercicio,
            conteudo_bytea=conteudo,
            tamanho_bytes=len(conteudo),
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_ECF,
            gerado_por_usuario_id=usuario_id,
            supersedes=anterior_arquivo.id if anterior_arquivo else None,
        )
        await sped_repo.criar(novo_arquivo)
        if anterior_arquivo is not None:
            await sped_repo.marcar_superseded(anterior_arquivo, novo_arquivo.id)

        lote = await lote_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            fonte="sped_ecf",
            arquivo_sped_id=novo_arquivo.id,
            nome_arquivo=nome_arquivo,
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_ECF,
        )

        resumo = _resumo_ecf(parseado)
        await lote_repo.concluir(lote.id, resumo=resumo)
        await session.commit()

        log.info(
            "migracao.lote.concluido",
            empresa_id=str(empresa_id),
            lote_id=str(lote.id),
            fonte="sped_ecf",
            trimestres_apuracao=len(parseado.apuracoes_trimestrais),
        )

        await session.refresh(lote)
        return ResultadoImportacaoEcf(lote=lote, reaproveitado=False)

    # ── EFD-Contribuições + EFD ICMS-IPI (PR3) ───────────────────────────────

    async def importar_sped_efd_contribuicoes(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        conteudo: bytes,
        nome_arquivo: str | None,
        usuario_id: uuid.UUID | None = None,
    ) -> ResultadoImportacaoEfd:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        try:
            parseado = parse_efd_contribuicoes(conteudo)
        except EfdContribuicoesInvalida as exc:
            raise SpedInvalido(f"EFD-Contribuições inválida: {exc}") from exc

        ident = parseado.identificacao
        if ident.cnpj != empresa.cnpj:
            raise EmpresaCnpjDivergente(
                f"CNPJ do SPED EFD-Contribuições ({ident.cnpj}) ≠ "
                f"CNPJ da empresa ({empresa.cnpj})"
            )
        if ident.competencia_inicio < PERIODO_INICIO_MINIMO:
            raise PeriodoForaCobertura(
                f"Período {ident.competencia_inicio} anterior ao corte "
                f"{PERIODO_INICIO_MINIMO}"
            )

        lote_repo = LoteImportacaoRepo(session)
        lote_anterior = await lote_repo.por_hash_concluido(
            empresa_id, parseado.hash_arquivo
        )
        if lote_anterior is not None:
            return ResultadoImportacaoEfd(lote=lote_anterior, reaproveitado=True)

        sped_repo = ArquivoSpedRepo(session)
        anterior_arquivo = await sped_repo.ativo(
            empresa_id,
            "efd_contribuicoes",
            ident.competencia_inicio,
            ident.competencia_fim,
        )
        novo_arquivo = ArquivoSped(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="efd_contribuicoes",
            periodo_inicio=ident.competencia_inicio,
            periodo_fim=ident.competencia_fim,
            conteudo_bytea=conteudo,
            tamanho_bytes=len(conteudo),
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_EFD_CONTRIB,
            gerado_por_usuario_id=usuario_id,
            supersedes=anterior_arquivo.id if anterior_arquivo else None,
        )
        await sped_repo.criar(novo_arquivo)
        if anterior_arquivo is not None:
            await sped_repo.marcar_superseded(anterior_arquivo, novo_arquivo.id)

        lote = await lote_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            fonte="sped_efd_contribuicoes",
            arquivo_sped_id=novo_arquivo.id,
            nome_arquivo=nome_arquivo,
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_EFD_CONTRIB,
        )

        criados, ja_existem, warnings = await self._persistir_documentos_efd(
            session,
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            documentos=parseado.documentos,
            cnpj_empresa=ident.cnpj,
        )

        resumo: JsonObject = {
            "cnpj_arquivo": ident.cnpj,
            "competencia_inicio": ident.competencia_inicio.isoformat(),
            "competencia_fim": ident.competencia_fim.isoformat(),
            "documentos_no_arquivo": len(parseado.documentos),
            "documentos_criados": criados,
            "documentos_ja_existem": ja_existem,
            "itens_total": sum(len(d.itens) for d in parseado.documentos),
            "apuracao_snapshot": parseado.apuracao_snapshot,
        }
        await lote_repo.concluir(
            lote.id,
            resumo=resumo,
            erros={"warnings": warnings} if warnings else None,
        )
        await session.commit()

        log.info(
            "migracao.lote.concluido",
            empresa_id=str(empresa_id),
            lote_id=str(lote.id),
            fonte="sped_efd_contribuicoes",
            documentos_criados=criados,
            documentos_ja_existem=ja_existem,
        )

        await session.refresh(lote)
        return ResultadoImportacaoEfd(lote=lote, reaproveitado=False)

    async def importar_sped_efd_icms_ipi(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        conteudo: bytes,
        nome_arquivo: str | None,
        usuario_id: uuid.UUID | None = None,
    ) -> ResultadoImportacaoEfd:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        try:
            parseado = parse_efd_icms_ipi(conteudo)
        except EfdIcmsIpiInvalida as exc:
            raise SpedInvalido(f"EFD ICMS-IPI inválida: {exc}") from exc

        ident = parseado.identificacao
        if ident.cnpj != empresa.cnpj:
            raise EmpresaCnpjDivergente(
                f"CNPJ do SPED EFD ICMS-IPI ({ident.cnpj}) ≠ "
                f"CNPJ da empresa ({empresa.cnpj})"
            )
        if ident.competencia_inicio < PERIODO_INICIO_MINIMO:
            raise PeriodoForaCobertura(
                f"Período {ident.competencia_inicio} anterior ao corte "
                f"{PERIODO_INICIO_MINIMO}"
            )

        lote_repo = LoteImportacaoRepo(session)
        lote_anterior = await lote_repo.por_hash_concluido(
            empresa_id, parseado.hash_arquivo
        )
        if lote_anterior is not None:
            return ResultadoImportacaoEfd(lote=lote_anterior, reaproveitado=True)

        sped_repo = ArquivoSpedRepo(session)
        anterior_arquivo = await sped_repo.ativo(
            empresa_id,
            "efd_icms_ipi",
            ident.competencia_inicio,
            ident.competencia_fim,
        )
        novo_arquivo = ArquivoSped(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="efd_icms_ipi",
            periodo_inicio=ident.competencia_inicio,
            periodo_fim=ident.competencia_fim,
            conteudo_bytea=conteudo,
            tamanho_bytes=len(conteudo),
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_EFD_ICMS_IPI,
            gerado_por_usuario_id=usuario_id,
            supersedes=anterior_arquivo.id if anterior_arquivo else None,
        )
        await sped_repo.criar(novo_arquivo)
        if anterior_arquivo is not None:
            await sped_repo.marcar_superseded(anterior_arquivo, novo_arquivo.id)

        lote = await lote_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            fonte="sped_efd_icms_ipi",
            arquivo_sped_id=novo_arquivo.id,
            nome_arquivo=nome_arquivo,
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_EFD_ICMS_IPI,
        )

        criados, ja_existem, warnings = await self._persistir_documentos_efd(
            session,
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            documentos=parseado.documentos,
            cnpj_empresa=ident.cnpj,
        )

        resumo = {
            "cnpj_arquivo": ident.cnpj,
            "competencia_inicio": ident.competencia_inicio.isoformat(),
            "competencia_fim": ident.competencia_fim.isoformat(),
            "documentos_no_arquivo": len(parseado.documentos),
            "documentos_criados": criados,
            "documentos_ja_existem": ja_existem,
            "itens_total": sum(len(d.itens) for d in parseado.documentos),
            "apuracao_icms_snapshot": parseado.apuracao_icms_snapshot,
        }
        await lote_repo.concluir(
            lote.id,
            resumo=resumo,
            erros={"warnings": warnings} if warnings else None,
        )
        await session.commit()

        await session.refresh(lote)
        return ResultadoImportacaoEfd(lote=lote, reaproveitado=False)

    async def _persistir_documentos_efd(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        documentos: tuple[DocumentoFiscalImportado, ...],
        cnpj_empresa: str | None = None,
    ) -> tuple[int, int, list[JsonObject]]:
        """Cria ``documento_fiscal`` + ``documento_fiscal_item`` para cada doc.

        Cross-check §8.9: se já existe documento com mesma ``chave`` para a
        empresa (UNIQUE parcial ``uq_doc_empresa_chave_vigente``), NÃO duplica
        — registra warning no lote. Quando a chave está vazia (NFS-e sem
        chave ABRASF), criamos sempre.

        Retorna ``(criados, ja_existem, warnings)``.
        """
        criados = 0
        ja_existem = 0
        warnings: list[JsonObject] = []

        # Pré-carrega chaves existentes em 1 query para evitar N+1.
        chaves_doc = [d.chave for d in documentos if d.chave]
        chaves_existentes: set[str] = set()
        if chaves_doc:
            stmt = select(DocumentoFiscal.chave).where(
                DocumentoFiscal.empresa_id == empresa_id,
                DocumentoFiscal.chave.in_(chaves_doc),
                DocumentoFiscal.superseded_by.is_(None),
            )
            rows = (await session.execute(stmt)).scalars().all()
            chaves_existentes = {c for c in rows if c is not None}

        for doc in documentos:
            if doc.chave and doc.chave in chaves_existentes:
                ja_existem += 1
                warnings.append(
                    {
                        "tipo": "documento_ja_existe",
                        "chave": doc.chave,
                        "numero": doc.numero,
                    }
                )
                continue

            doc_id = uuid.uuid4()
            # Sprint 19.7 PR3 (#36) — CNPJ via 0150 com fall-back consciente.
            # Para 'entrada' (NF de fornecedor): emitente = participante
            # (CNPJ vindo do 0150 do COD_PART). Para 'saida' (NF emitida
            # pela empresa): emitente = empresa, destinatário = participante.
            cnpj_emit, cnpj_dest = _resolver_emit_dest(
                doc.direcao,
                cnpj_empresa=cnpj_empresa,
                cnpj_participante=doc.cnpj_participante,
            )
            modelo_db = DocumentoFiscal(
                id=doc_id,
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                tipo=doc.tipo,
                direcao=doc.direcao,
                chave=doc.chave,
                numero=doc.numero,
                serie=doc.serie,
                status="cancelada" if doc.cancelado else "autorizada",
                emitida_em=_aware_meio_dia(doc.emitida_em),
                cnpj_emitente=cnpj_emit,
                cnpj_destinatario=cnpj_dest,
                valor_total=doc.valor_total,
                valor_pis=doc.valor_pis,
                valor_cofins=doc.valor_cofins,
                cfop=doc.cfop,
                ingested_via="importacao_sped",
            )
            modelo_db.itens = [
                DocumentoFiscalItem(
                    tenant_id=tenant_id,
                    documento_fiscal_id=doc_id,
                    n_item=it.n_item,
                    codigo_produto=it.codigo_produto,
                    descricao=it.descricao,
                    cfop=it.cfop,
                    cst_icms=it.cst_icms,
                    cst_pis=it.cst_pis,
                    cst_cofins=it.cst_cofins,
                    unidade=it.unidade,
                    quantidade=it.quantidade,
                    valor_unitario=(
                        (it.valor_total / it.quantidade)
                        if it.quantidade > 0
                        else it.valor_total
                    ),
                    valor_total=it.valor_total,
                    valor_icms=it.valor_icms,
                    valor_pis=it.valor_pis,
                    valor_cofins=it.valor_cofins,
                )
                for it in doc.itens
            ]
            session.add(modelo_db)
            criados += 1

        await session.flush()
        return criados, ja_existem, warnings

    # ── CSV (PR3) ────────────────────────────────────────────────────────────

    async def importar_csv_balancete(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        conteudo: bytes,
        nome_arquivo: str | None,
        usuario_id: uuid.UUID | None = None,
    ) -> ResultadoImportacaoCsv:
        """Importa balancete CSV — snapshot read-only em ``resumo_jsonb``.

        NÃO cria lançamentos contábeis — usa apenas para o front exibir
        comparativo com o balancete recalculado por cima de NF-e/lançamentos
        importados via outras fontes.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        try:
            parseado = parse_balancete_csv(conteudo)
        except CsvInvalido as exc:
            raise SpedInvalido(f"CSV balancete inválido: {exc}") from exc

        lote_repo = LoteImportacaoRepo(session)
        lote_anterior = await lote_repo.por_hash_concluido(
            empresa_id, parseado.hash_arquivo
        )
        if lote_anterior is not None:
            return ResultadoImportacaoCsv(
                lote=lote_anterior, reaproveitado=True
            )

        lote = await lote_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            fonte="csv_balancete",
            arquivo_sped_id=None,
            nome_arquivo=nome_arquivo,
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_CSV,
        )

        resumo = _resumo_balancete(parseado)
        await lote_repo.concluir(lote.id, resumo=resumo)
        await session.commit()

        log.info(
            "migracao.lote.concluido",
            empresa_id=str(empresa_id),
            lote_id=str(lote.id),
            fonte="csv_balancete",
            contas=len(parseado.linhas),
        )

        await session.refresh(lote)
        return ResultadoImportacaoCsv(lote=lote, reaproveitado=False)

    async def importar_csv_razao(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        conteudo: bytes,
        nome_arquivo: str | None,
        usuario_id: uuid.UUID | None = None,
    ) -> ResultadoImportacaoCsv:
        """Importa razão CSV — gera ``LancamentoCandidato`` por linha.

        Cada linha vira um lançamento contábil com débito em
        ``conta_debito`` + crédito em ``conta_credito`` (idempotência §8.9
        via ``origem_id=uuid5(hash_arquivo + linha)``). Contas ausentes do
        plano viram warning + skip.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        try:
            parseado = parse_razao_csv(conteudo)
        except CsvInvalido as exc:
            raise SpedInvalido(f"CSV razão inválido: {exc}") from exc

        lote_repo = LoteImportacaoRepo(session)
        lote_anterior = await lote_repo.por_hash_concluido(
            empresa_id, parseado.hash_arquivo
        )
        if lote_anterior is not None:
            return ResultadoImportacaoCsv(
                lote=lote_anterior, reaproveitado=True
            )

        lote = await lote_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            fonte="csv_razao",
            arquivo_sped_id=None,
            nome_arquivo=nome_arquivo,
            hash_arquivo=parseado.hash_arquivo,
            algoritmo_versao=ALGORITMO_CSV,
        )

        conta_repo = ContaContabilRepo(session)
        cache_conta: dict[tuple[str, date], uuid.UUID | None] = {}

        async def conta_id_por_codigo(
            codigo: str, em: date
        ) -> uuid.UUID | None:
            chave = (codigo, em)
            if chave in cache_conta:
                return cache_conta[chave]
            conta = await conta_repo.por_codigo(empresa_id, codigo, em=em)
            cache_conta[chave] = conta.id if conta is not None else None
            return cache_conta[chave]

        criados = 0
        existentes = 0
        pulados = 0
        warnings: list[JsonObject] = []
        chaves_referenciadas: set[str] = set()

        for n, lanc_csv in enumerate(parseado.lancamentos, start=1):
            conta_d = await conta_id_por_codigo(lanc_csv.conta_debito, lanc_csv.data)
            conta_c = await conta_id_por_codigo(
                lanc_csv.conta_credito, lanc_csv.data
            )
            ausente: str | None = None
            if conta_d is None:
                ausente = lanc_csv.conta_debito
            elif conta_c is None:
                ausente = lanc_csv.conta_credito
            if ausente is not None:
                pulados += 1
                warnings.append(
                    {
                        "tipo": "conta_ausente",
                        "linha": n,
                        "codigo_conta": ausente,
                        "data_lancamento": lanc_csv.data.isoformat(),
                    }
                )
                continue

            assert conta_d is not None and conta_c is not None
            origem_id = uuid.uuid5(
                _NS_MIGRACAO_LANC, f"{parseado.hash_arquivo}|{n}"
            )
            candidato = LancamentoCandidato(
                historico=lanc_csv.historico[:500],
                data_lancamento=lanc_csv.data,
                competencia=date(lanc_csv.data.year, lanc_csv.data.month, 1),
                origem_tipo="importacao",
                origem_id=origem_id,
                partidas=(
                    PartidaCandidata(
                        conta_id=conta_d,
                        tipo="D",
                        valor=lanc_csv.valor,
                    ),
                    PartidaCandidata(
                        conta_id=conta_c,
                        tipo="C",
                        valor=lanc_csv.valor,
                    ),
                ),
                versao=ALGORITMO_CSV,
            )
            resultado = await self._lancador._persistir(
                session, tenant_id, empresa_id, candidato
            )
            if resultado is True:
                criados += 1
            elif resultado is False:
                existentes += 1
            if lanc_csv.chave_nfe_referenciada is not None:
                chaves_referenciadas.add(lanc_csv.chave_nfe_referenciada)

        resumo = {
            "linhas_no_arquivo": len(parseado.lancamentos),
            "lancamentos_criados": criados,
            "lancamentos_existentes": existentes,
            "lancamentos_pulados": pulados,
            "total_valor": str(parseado.total_valor),
            "chaves_nfe_referenciadas": sorted(chaves_referenciadas),
        }
        await lote_repo.concluir(
            lote.id,
            resumo=resumo,
            erros={"warnings": warnings} if warnings else None,
        )
        await session.commit()

        log.info(
            "migracao.lote.concluido",
            empresa_id=str(empresa_id),
            lote_id=str(lote.id),
            fonte="csv_razao",
            criados=criados,
            pulados=pulados,
        )

        await session.refresh(lote)
        return ResultadoImportacaoCsv(lote=lote, reaproveitado=False)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _aware_meio_dia(d: date) -> datetime:
    """Converte ``date`` em ``datetime`` aware no fuso BR (meio-dia para evitar borda).

    Usado quando importamos documentos fiscais que vêm com data sem hora
    (EFD agrega por data de emissão).
    """
    return datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=_TZ_BR)


def tenant_cnpj_placeholder() -> str:
    """CNPJ placeholder ``"00000000000000"`` — só usado como último recurso.

    Sprint 19.7 PR3 (#36) resolveu a pendência: o gerador agora extrai
    o CNPJ real do participante via ``_resolver_emit_dest`` (lookup do
    0150). Este helper sobrevive apenas pra ambientes onde o arquivo
    importado vier sem 0000 (cnpj_empresa vazio) **e** sem 0150 com
    CNPJ — cenário patológico (arquivo SPED estruturalmente quebrado).
    """
    return "00000000000000"


def _resolver_emit_dest(
    direcao: str,
    *,
    cnpj_empresa: str | None,
    cnpj_participante: str | None,
) -> tuple[str, str | None]:
    """Aplica a regra fiscal: quem emite × quem recebe (Sprint 19.7 PR3 #36).

    Regras (alinhado a §3 do Manual do EFD-Contribuições):

      * ``direcao='saida'``  → empresa emite NF; participante é cliente.
        emitente = ``cnpj_empresa`` (sempre presente em arquivo válido).
        destinatário = ``cnpj_participante`` (pode ser ``None`` em B2C).

      * ``direcao='entrada'`` → empresa recebe NF; participante é
        fornecedor. emitente = ``cnpj_participante`` (resolvido via
        0150). destinatário = ``cnpj_empresa``.

    Em casos onde o CNPJ esperado não está disponível (arquivo
    incompleto), cai em ``tenant_cnpj_placeholder()`` — mantém persistência
    sem violar `NOT NULL` mas sinaliza no log.
    """
    placeholder = tenant_cnpj_placeholder()
    if direcao == "saida":
        emit = cnpj_empresa or placeholder
        dest = cnpj_participante
    else:  # 'entrada' (ou qualquer outra direção — fail-safe)
        emit = cnpj_participante or placeholder
        dest = cnpj_empresa
    return emit, dest


def _resumo_balancete(parseado: BalanceteParseado) -> JsonObject:
    """Snapshot do balancete CSV para ``lote.resumo_jsonb``.

    Decimal → str (determinismo na serialização JSONB). Inclui as linhas
    completas (chartof-accounts pode ser pequeno, < 200 contas).
    """
    linhas_json = [
        {
            "codigo_conta": ln.codigo_conta,
            "descricao": ln.descricao,
            "saldo_inicial": str(ln.saldo_inicial),
            "debito": str(ln.debito),
            "credito": str(ln.credito,),
            "saldo_final": str(ln.saldo_final),
        }
        for ln in parseado.linhas
    ]
    return {
        "contas": len(parseado.linhas),
        "total_debitos": str(parseado.total_debitos),
        "total_creditos": str(parseado.total_creditos),
        "linhas": linhas_json,
    }


class _LookupCallable:
    """Tipo do callable de lookup conta_id_por_codigo — só para mypy."""

    async def __call__(self, codigo: str, em: date) -> uuid.UUID | None: ...


def _origem_id(arquivo_sped_id: uuid.UUID, numero_lancamento: str) -> uuid.UUID:
    """UUID5 determinístico — idempotência §8.9 do lançamento importado.

    Usa namespace fixo ``_NS_MIGRACAO_LANC`` + ``arquivo_sped_id|numero``.
    Mesmo arquivo SPED reimportado (com hash diferente — caso raro) gera
    o **mesmo** ``origem_id``, então ``_persistir`` devolve ``False`` em
    todas as linhas — sem duplicação no DB.
    """
    base = f"{arquivo_sped_id}|{numero_lancamento}"
    return uuid.uuid5(_NS_MIGRACAO_LANC, base)


def _historico_lancamento(lanc: LancamentoEcdParseado) -> str:
    """Concatena históricos das partidas — fonte primária do lançamento."""
    historicos = [p.historico for p in lanc.partidas if p.historico]
    if historicos:
        # Primeiro histórico não-vazio costuma ser o canônico no SPED.
        return historicos[0][:500]
    return f"Importação SPED ECD — lançamento {lanc.numero}"


def _resumo_ecf(parseado: EcfParseado) -> JsonObject:
    """Materializa snapshot das apurações para ``lote.resumo_jsonb``.

    Decimal → str para serialização determinística (idem padrão do
    Sprint 13 PR2 snapshot empresa).
    """
    apuracoes_json: list[dict[str, str]] = []
    for ap in parseado.apuracoes_trimestrais:
        apuracoes_json.append(
            {
                "inicio": ap.inicio.isoformat(),
                "fim": ap.fim.isoformat(),
                "receita_bruta": str(ap.receita_bruta),
                "base_presumida_irpj": str(ap.base_presumida_irpj),
                "base_total_irpj": str(ap.base_total_irpj),
                "irpj_normal": str(ap.irpj_normal),
                "irpj_adicional": str(ap.irpj_adicional),
                "irpj_total": str(ap.irpj_total),
                "irpj_devido": str(ap.irpj_devido),
                "base_total_csll": str(ap.base_total_csll),
                "csll_devida": str(ap.csll_devida),
            }
        )
    irpj_total_ano = sum(
        (ap.irpj_devido for ap in parseado.apuracoes_trimestrais),
        start=Decimal("0"),
    )
    csll_total_ano = sum(
        (ap.csll_devida for ap in parseado.apuracoes_trimestrais),
        start=Decimal("0"),
    )
    return {
        "cnpj_arquivo": parseado.identificacao.cnpj,
        "inicio_exercicio": parseado.identificacao.inicio_exercicio.isoformat(),
        "fim_exercicio": parseado.identificacao.fim_exercicio.isoformat(),
        "forma_tributacao": parseado.identificacao.forma_tributacao,
        "trimestres_apuracao": len(parseado.apuracoes_trimestrais),
        "apuracoes": apuracoes_json,
        "irpj_total_ano_declarado": str(irpj_total_ano),
        "csll_total_ano_declarado": str(csll_total_ano),
    }
