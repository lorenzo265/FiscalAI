"""Repositório — NF-e Destinada + Cursor de DistribuiçãoDFe (MD-e PR2).

Operações async sobre ``nfe_destinada`` e ``nfe_distribuicao_cursor``.
Upsert idempotente: ``(empresa_id, chave_nfe)`` é a chave natural;
em colisão atualiza em vez de duplicar (§8.9).

Sem N+1: todas as queries são filtradas por ``empresa_id`` (RLS garante
isolamento cross-tenant). ``selectinload`` não aplicável aqui (sem joins
necessários); as queries são simples SELECTs pontuais.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import ManifestacaoNFe, NfeDestinada, NfeDistribuicaoCursor
from app.shared.integrations.sefaz_mde.types import ResumoNFeDestinada


class DistribuicaoRepo:
    """Acesso a dados do DistribuiçãoDFe — NF-e destinada e cursor de NSU."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── Cursor ───────────────────────────────────────────────────────────────

    async def get_cursor(self, empresa_id: UUID) -> NfeDistribuicaoCursor | None:
        """Retorna o cursor de NSU da empresa, ou None se não existir."""
        stmt = select(NfeDistribuicaoCursor).where(
            NfeDistribuicaoCursor.empresa_id == empresa_id
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def create_cursor(
        self,
        tenant_id: UUID,
        empresa_id: UUID,
    ) -> NfeDistribuicaoCursor:
        """Cria cursor inicial (ult_nsu = 0, max_nsu = 0) para a empresa."""
        cursor = NfeDistribuicaoCursor(
            empresa_id=empresa_id,
            tenant_id=tenant_id,
            ult_nsu=0,
            max_nsu=0,
            ultima_sync_em=None,
        )
        self._s.add(cursor)
        await self._s.flush()
        return cursor

    async def update_cursor(
        self,
        cursor: NfeDistribuicaoCursor,
        *,
        ult_nsu: int,
        max_nsu: int,
        ultima_sync_em: datetime,
    ) -> NfeDistribuicaoCursor:
        """Atualiza o cursor após um batch de sincronização."""
        cursor.ult_nsu = ult_nsu
        cursor.max_nsu = max_nsu
        cursor.ultima_sync_em = ultima_sync_em
        await self._s.flush()
        return cursor

    # ── NF-e Destinada ───────────────────────────────────────────────────────

    async def upsert_destinada(
        self,
        tenant_id: UUID,
        empresa_id: UUID,
        doc: ResumoNFeDestinada,
        agora: datetime,
    ) -> tuple[NfeDestinada, bool]:
        """Insere ou atualiza um documento em ``nfe_destinada``.

        Retorna ``(objeto, is_new)`` onde ``is_new=True`` indica inserção.
        Idempotência: chamadas repetidas com a mesma ``chave_nfe`` atualizam
        em vez de duplicar (§8.9). Quando um ``resNFe`` (resumo) é seguido
        de um ``nfeProc`` (completo), ``tipo_documento`` e ``tem_xml_completo``
        são promovidos corretamente.
        """
        stmt = select(NfeDestinada).where(
            NfeDestinada.empresa_id == empresa_id,
            NfeDestinada.chave_nfe == doc.chave_nfe,
        )
        result = await self._s.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            obj = NfeDestinada(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                chave_nfe=doc.chave_nfe,
                nsu=doc.nsu,
                emitente_cnpj=doc.emitente_cnpj,
                emitente_nome=doc.emitente_nome,
                valor_total=doc.valor_total,
                dh_emissao=doc.dh_emissao,
                tipo_documento=doc.tipo_documento,
                tem_xml_completo=doc.xml_completo is not None,
                xml_storage_key=None,  # write I/O ao storage: PR3
                criado_em=agora,
                atualizado_em=agora,
            )
            self._s.add(obj)
            await self._s.flush()
            return obj, True

        # Atualiza campos com dados mais recentes.
        # NSU: mantém o maior (documentos chegam em ordem crescente de NSU,
        # mas em re-sync o mesmo documento pode chegar com NSU menor se o
        # cursor foi resetado).
        existing.nsu = max(existing.nsu, doc.nsu)
        # Emitente: aceita dados não-nulos do payload mais recente
        if doc.emitente_cnpj:
            existing.emitente_cnpj = doc.emitente_cnpj
        if doc.emitente_nome:
            existing.emitente_nome = doc.emitente_nome
        if doc.valor_total is not None:
            existing.valor_total = doc.valor_total
        if doc.dh_emissao is not None:
            existing.dh_emissao = doc.dh_emissao
        # Promoção resumo → completo (nunca retroage de completo para resumo)
        if doc.tipo_documento == "completo":
            existing.tipo_documento = "completo"
            existing.tem_xml_completo = True
        existing.atualizado_em = agora
        await self._s.flush()
        return existing, False

    async def listar_destinadas(
        self,
        empresa_id: UUID,
        *,
        pendentes: bool = False,
        limite: int = 100,
    ) -> list[NfeDestinada]:
        """Lista NF-es destinadas de uma empresa.

        ``pendentes=True`` filtra apenas as que ainda não possuem nenhuma
        linha em ``manifestacao_nfe`` para a mesma chave — i.e., o destinatário
        ainda não manifestou (Confirmação, Ciência, Desconhecimento ou
        Não Realizada) sobre aquela NF-e.

        Ordenado por NSU decrescente (mais recentes primeiro).
        """
        if pendentes:
            # LEFT JOIN com manifestacao_nfe; inclui apenas linhas sem match.
            stmt = (
                select(NfeDestinada)
                .outerjoin(
                    ManifestacaoNFe,
                    (ManifestacaoNFe.empresa_id == NfeDestinada.empresa_id)
                    & (ManifestacaoNFe.chave_nfe == NfeDestinada.chave_nfe),
                )
                .where(
                    NfeDestinada.empresa_id == empresa_id,
                    ManifestacaoNFe.id.is_(None),
                )
                .order_by(NfeDestinada.nsu.desc())
                .limit(limite)
            )
        else:
            stmt = (
                select(NfeDestinada)
                .where(NfeDestinada.empresa_id == empresa_id)
                .order_by(NfeDestinada.nsu.desc())
                .limit(limite)
            )
        result = await self._s.execute(stmt)
        return list(result.scalars().all())
