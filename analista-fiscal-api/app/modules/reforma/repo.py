"""Repositórios da Reforma (Sprint 14 PR1 + PR3).

PR1: ``AliquotaCbsIbsRepo`` — SCD lookup de alíquotas.
PR3: ``ReformaRepo`` — queries auxiliares (apurações 12m + documentos do ano).

Sprint 19 PR2: ``AliquotaCbsIbsRepo`` aceita ``Cache`` opcional via DI para
evitar hit no DB em SCD lookups read-mostly (cache-aside §8.10).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fiscal.snapshots import parse_apuracao_output
from app.modules.reforma.calcula_cbs_ibs import AliquotaCBSIBS
from app.modules.reforma.periodo_transicao import FaseReforma, fase
from app.shared.cache import Cache, aliquota_cbs_ibs_key
from app.shared.db.models import AliquotaCbsIbs, ApuracaoFiscal, DocumentoFiscal
from app.shared.exceptions import AliquotaCbsIbsAusente

# SCD CBS/IBS: tabela tributária com vigências em datas-chave (2026, 2027,
# 2033). Mudanças entram via INSERT de nova linha SCD — invalidação por
# pattern ``scd:cbs_ibs:*`` quando contador insere nova vigência.
_CACHE_TTL_SCD_CBS_IBS = 86400  # 24h


def _para_dataclass(row: AliquotaCbsIbs) -> AliquotaCBSIBS:
    """Converte ORM row em dataclass frozen do algoritmo puro."""
    return AliquotaCBSIBS(
        fase=FaseReforma(row.fase),
        aliquota_cbs=row.aliquota_cbs,
        aliquota_ibs=row.aliquota_ibs,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        fonte_norma=row.fonte_norma,
        algoritmo_versao=row.algoritmo_versao,
        observacao=row.observacao,
    )


def _especificidade(
    row: AliquotaCbsIbs,
    *,
    regime: str | None,
    cnae: str | None,
    classificacao: str | None,
) -> tuple[int, int, int]:
    """Score para desempate: linhas com filtros NOT NULL pontuam mais.

    Ordem dos pesos: regime → classificacao → cnae_pattern. Quanto maior o
    score, mais específico (e melhor candidato).
    """

    def match(target: str | None, pattern: str | None) -> int:
        if pattern is None:
            return 0  # vigência geral
        if target is None:
            return -1  # filtro pede algo que cliente não tem → não casa
        # cnae usa prefix match; demais usam igualdade
        return 1 if target == pattern else 0

    score_regime = match(regime, row.regime)
    score_classif = match(classificacao, row.classificacao_lc214)
    if row.cnae_pattern is None:
        score_cnae = 0
    elif cnae is None:
        score_cnae = -1
    elif cnae.startswith(row.cnae_pattern):
        # Prefix match — pattern mais longo é mais específico.
        score_cnae = len(row.cnae_pattern)
    else:
        score_cnae = -1
    return (score_regime, score_classif, score_cnae)


def _encode_aliquota(a: AliquotaCBSIBS) -> str:
    """Serializa ``AliquotaCBSIBS`` para JSON (Decimal/date como string).

    Não usa ``dataclasses.asdict`` direto para manter controle do schema —
    se a dataclass crescer com campo novo, o cache invalida-se naturalmente
    via ``_decode_aliquota`` (KeyError → cai no loader e refaz).
    """
    return json.dumps(
        {
            "fase": a.fase.value,
            "aliquota_cbs": str(a.aliquota_cbs),
            "aliquota_ibs": str(a.aliquota_ibs),
            "valid_from": a.valid_from.isoformat(),
            "valid_to": a.valid_to.isoformat() if a.valid_to else None,
            "fonte_norma": a.fonte_norma,
            "algoritmo_versao": a.algoritmo_versao,
            "observacao": a.observacao,
        }
    )


def _decode_aliquota(raw: str) -> AliquotaCBSIBS:
    """Reconstrói ``AliquotaCBSIBS`` do JSON. KeyError vira miss intencional."""
    d = json.loads(raw)
    return AliquotaCBSIBS(
        fase=FaseReforma(d["fase"]),
        aliquota_cbs=Decimal(d["aliquota_cbs"]),
        aliquota_ibs=Decimal(d["aliquota_ibs"]),
        valid_from=date.fromisoformat(d["valid_from"]),
        valid_to=date.fromisoformat(d["valid_to"]) if d["valid_to"] else None,
        fonte_norma=d["fonte_norma"],
        algoritmo_versao=d["algoritmo_versao"],
        observacao=d.get("observacao"),
    )


class AliquotaCbsIbsRepo:
    """Leitura SCD (§8.3) de ``aliquota_cbs_ibs`` resolvendo a vigência mais
    específica para uma competência.

    Sprint 19 PR2: cache opcional via DI. Quando ``cache`` é passado, a
    lookup vai pelo Redis primeiro (TTL 24h + jitter ±10% + SETNX lock
    contra thundering herd). Quando ``None``, comportamento original.
    """

    def __init__(self, session: AsyncSession, cache: Cache | None = None) -> None:
        self._s = session
        self._cache = cache

    async def vigente(
        self,
        competencia: date,
        *,
        regime: str | None = None,
        cnae: str | None = None,
        classificacao: str | None = None,
    ) -> AliquotaCBSIBS:
        """Retorna a vigência mais específica vigente em ``competencia``.

        A fase é derivada de ``periodo_transicao.fase(competencia)``; só se
        consideram linhas dessa fase. Filtros (regime/cnae/classificacao)
        funcionam como **scoring** — uma vigência geral (todos os campos
        NULL) sempre casa; mais específica vence o desempate.

        Args:
            competencia: data dentro do mês.
            regime: ``simples_nacional``/``lucro_presumido``/``lucro_real``
                (opcional — defaults para geral).
            cnae: CNAE da empresa (opcional). Match por prefixo.
            classificacao: ``geral``/``reducao_60``/``reducao_30``/
                ``regime_diferenciado`` (LC 214 art. 9º).

        Returns:
            AliquotaCBSIBS resolvida.

        Raises:
            AliquotaCbsIbsAusente: nenhuma vigência cobre a competência
                (gap de seed — defeito operacional).
            PeriodoReformaNaoMapeado: competência anterior a 2026-01-01.
        """
        if self._cache is None:
            return await self._resolver_db(
                competencia,
                regime=regime,
                cnae=cnae,
                classificacao=classificacao,
            )

        key = aliquota_cbs_ibs_key(
            competencia, regime=regime, cnae=cnae, classificacao=classificacao,
        )

        async def _loader() -> str:
            # Exceções (AliquotaCbsIbsAusente / PeriodoReformaNaoMapeado)
            # NÃO entram no cache — só sucesso. Cache de erro é armadilha:
            # se o seed for corrigido, a falha fica grudada por 24h.
            resolvida = await self._resolver_db(
                competencia,
                regime=regime,
                cnae=cnae,
                classificacao=classificacao,
            )
            return _encode_aliquota(resolvida)

        raw = await self._cache.get_or_compute(
            key, _loader, ttl=_CACHE_TTL_SCD_CBS_IBS,
        )
        return _decode_aliquota(raw)

    async def _resolver_db(
        self,
        competencia: date,
        *,
        regime: str | None,
        cnae: str | None,
        classificacao: str | None,
    ) -> AliquotaCBSIBS:
        """Query original — fonte de verdade para cache miss."""
        fase_alvo = fase(competencia)
        stmt = (
            select(AliquotaCbsIbs)
            .where(AliquotaCbsIbs.fase == fase_alvo.value)
            .where(AliquotaCbsIbs.valid_from <= competencia)
            .where(
                (AliquotaCbsIbs.valid_to.is_(None))
                | (AliquotaCbsIbs.valid_to > competencia)
            )
        )
        linhas = list((await self._s.execute(stmt)).scalars().all())

        candidatos: list[tuple[tuple[int, int, int], AliquotaCbsIbs]] = []
        for row in linhas:
            score = _especificidade(
                row, regime=regime, cnae=cnae, classificacao=classificacao,
            )
            if score[0] < 0 or score[1] < 0 or score[2] < 0:
                continue  # filtro NOT NULL exige algo que cliente não tem
            candidatos.append((score, row))

        if not candidatos:
            raise AliquotaCbsIbsAusente(
                f"Sem vigência de aliquota_cbs_ibs para fase={fase_alvo.value} "
                f"em {competencia.isoformat()} (regime={regime}, cnae={cnae}, "
                f"classificacao={classificacao}). Seed incompleto."
            )

        # Mais específico vence; em empate, valid_from mais recente.
        candidatos.sort(key=lambda c: (c[0], c[1].valid_from), reverse=True)
        return _para_dataclass(candidatos[0][1])


# ── PR3 — queries auxiliares para o simulador + backfill ────────────────────


@dataclass(frozen=True, slots=True)
class CargaApurada12m:
    """Soma por tipo das apurações fiscais dos últimos 12 meses."""

    pis: Decimal
    cofins: Decimal
    icms: Decimal
    iss: Decimal
    receita_anualizada: Decimal
    icms_medio_mensal: Decimal
    periodo_inicio: date
    periodo_fim: date

    @property
    def total(self) -> Decimal:
        return self.pis + self.cofins + self.icms + self.iss

    @property
    def vazia(self) -> bool:
        """True se nenhuma apuração foi encontrada nos 12m."""
        return (
            self.pis == Decimal("0")
            and self.cofins == Decimal("0")
            and self.icms == Decimal("0")
            and self.iss == Decimal("0")
            and self.receita_anualizada == Decimal("0")
        )


_DELTA_UM_DIA = timedelta(days=1)


def _periodo_12m_ate(competencia: date) -> tuple[date, date]:
    """Retorna (inicio, fim) cobrindo os 12m anteriores a ``competencia``.

    ``fim`` = último dia do mês anterior à competência.
    ``inicio`` = primeiro dia do mês 11 meses antes do fim (12 meses ao todo).
    """
    fim_mes = competencia.replace(day=1) - _DELTA_UM_DIA
    ano_inicio = fim_mes.year - 1
    mes_inicio = fim_mes.month + 1
    if mes_inicio > 12:
        mes_inicio -= 12
        ano_inicio += 1
    inicio = date(ano_inicio, mes_inicio, 1)
    return inicio, fim_mes


class ReformaRepo:
    """Queries auxiliares — apurações 12m + documentos do ano (PR3)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def carga_apurada_12m(
        self, empresa_id: UUID, competencia: date
    ) -> CargaApurada12m:
        """Soma PIS+Cofins+ICMS+ISS dos últimos 12m + receita + ICMS médio.

        Tipos buscados em ``apuracao_fiscal``:
          * ``pis``, ``cofins``  — mensais (Lucro Presumido).
          * ``icms``             — mensais.
          * ``iss``              — NFS-e (quando aplicável).

        Receita anualizada vem de ``documento_fiscal`` (direcao='saida',
        status='autorizada', superseded_by IS NULL) somando ``valor_total``.
        """
        inicio, fim = _periodo_12m_ate(competencia)

        # Apurações por tipo
        stmt_apur = select(ApuracaoFiscal).where(
            ApuracaoFiscal.empresa_id == empresa_id,
            ApuracaoFiscal.competencia >= inicio,
            ApuracaoFiscal.competencia <= fim,
            ApuracaoFiscal.tipo.in_(("pis", "cofins", "icms", "iss")),
        )
        agregados: dict[str, Decimal] = {
            "pis": Decimal("0"),
            "cofins": Decimal("0"),
            "icms": Decimal("0"),
            "iss": Decimal("0"),
        }
        for ap in (await self._s.execute(stmt_apur)).scalars().all():
            snap = parse_apuracao_output(
                ap.tipo, ap.output_jsonb, input_jsonb=ap.input_jsonb
            )
            agregados[ap.tipo] += snap.valor_devido

        # Receita anualizada (soma valor_total saídas autorizadas no período)
        stmt_receita = (
            select(func.coalesce(func.sum(DocumentoFiscal.valor_total), 0))
            .where(DocumentoFiscal.empresa_id == empresa_id)
            .where(DocumentoFiscal.direcao == "saida")
            .where(DocumentoFiscal.status == "autorizada")
            .where(DocumentoFiscal.superseded_by.is_(None))
            .where(DocumentoFiscal.emitida_em >= inicio)
            .where(DocumentoFiscal.emitida_em <= fim)
        )
        receita_raw = (await self._s.execute(stmt_receita)).scalar_one()
        receita = Decimal(receita_raw)

        # ICMS médio mensal — usa qty de meses com apuração ICMS para evitar
        # subestimar com meses zero. Mínimo 1 mês para não dividir por zero.
        icms_total = agregados["icms"]
        stmt_meses_icms = (
            select(func.count())
            .select_from(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.competencia >= inicio)
            .where(ApuracaoFiscal.competencia <= fim)
            .where(ApuracaoFiscal.tipo == "icms")
        )
        meses_icms = max(1, int((await self._s.execute(stmt_meses_icms)).scalar_one()))
        icms_medio_mensal = (icms_total / Decimal(meses_icms)).quantize(
            Decimal("0.01")
        )

        return CargaApurada12m(
            pis=agregados["pis"],
            cofins=agregados["cofins"],
            icms=agregados["icms"],
            iss=agregados["iss"],
            receita_anualizada=receita,
            icms_medio_mensal=icms_medio_mensal,
            periodo_inicio=inicio,
            periodo_fim=fim,
        )

    async def documentos_do_ano_sem_cbs(
        self, empresa_id: UUID, ano: int, *, forcar: bool = False
    ) -> list[DocumentoFiscal]:
        """Lista documentos da empresa naquele ano para backfill informacional.

        Args:
            empresa_id: empresa-alvo (RLS-protegida).
            ano: ano civil (ex.: 2026).
            forcar: quando ``False`` (default), só devolve documentos com
                ``valor_cbs IS NULL OR valor_ibs IS NULL``. Quando ``True``,
                devolve todos do ano (uso administrativo — recálculo).
        """
        inicio = date(ano, 1, 1)
        fim = date(ano, 12, 31)
        stmt = (
            select(DocumentoFiscal)
            .where(DocumentoFiscal.empresa_id == empresa_id)
            .where(DocumentoFiscal.emitida_em >= inicio)
            .where(DocumentoFiscal.emitida_em <= fim)
            .where(DocumentoFiscal.superseded_by.is_(None))
        )
        if not forcar:
            stmt = stmt.where(
                (DocumentoFiscal.valor_cbs.is_(None))
                | (DocumentoFiscal.valor_ibs.is_(None))
            )
        return list((await self._s.execute(stmt)).scalars().all())

    async def atualizar_cbs_ibs_documento(
        self,
        documento_id: UUID,
        *,
        valor_cbs: Decimal,
        valor_ibs: Decimal,
    ) -> None:
        """UPDATE pontual de valor_cbs/valor_ibs em ``documento_fiscal``.

        Campos informacionais — não viola §8.2 (que protege chave/valor_total).
        Migration 0024 fez REVOKE UPDATE FROM PUBLIC, mas o worker e o
        service rodam como superuser fiscal (que ainda tem UPDATE).
        """
        stmt = (
            update(DocumentoFiscal)
            .where(DocumentoFiscal.id == documento_id)
            .values(valor_cbs=valor_cbs, valor_ibs=valor_ibs)
        )
        await self._s.execute(stmt)
