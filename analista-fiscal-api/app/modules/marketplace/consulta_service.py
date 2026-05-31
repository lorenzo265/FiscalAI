"""Service do ciclo de vida de ``consulta_marketplace`` (Sprint 13 PR2).

Pipeline:

  1. ``criar(...)`` — cliente PME abre consulta. Idempotente por dia/categoria/
     pergunta (uuid5). Calcula SLA timestamps + comissão a partir da
     ``Pricing`` da categoria. Snapshot da empresa preservado (snapshot v1).
     Status inicial: ``aberta`` (sem contador escolhido) ou ``atribuida``
     (cliente já escolheu um dos top-3).

  2. ``aceitar(...)`` — parceiro confirma. ``atribuida → aceita``. Falha se
     ``sla_aceitar_ate`` venceu.

  3. ``responder(...)`` — parceiro envia resposta. ``aceita`` ou
     ``em_andamento`` → ``concluida``. Falha se ``sla_responder_ate`` venceu.

  4. ``avaliar(...)`` — cliente PME avalia (1–5). ``concluida`` → ``concluida``
     (status não muda, mas rating do parceiro é recalculado).

Princípios cravados: §8.7 (consentimento obrigatório), §8.8 (LLM não escreve
fato — cliente é quem POSTa), §8.9 (idempotency_key uuid5 cravada em DB),
§8.10 (log estruturado em cada transição).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.marketplace.categorias import comissao, pricing_para
from app.modules.marketplace.especialidades import especialidade_para
from app.modules.marketplace.repo import ConsultaRepo, ContadorParceiroRepo
from app.modules.marketplace.snapshot import SNAPSHOT_VERSAO, snapshot_empresa
from app.shared.db.models import ConsultaMarketplace, ContadorParceiro
from app.shared.db.rls import set_contador_id
from app.shared.exceptions import (
    ConsentimentoAusente,
    ConsultaForaDeFluxo,
    ConsultaJaAvaliada,
    ConsultaNaoEncontrada,
    ConsultaSlaExpirado,
    ContadorParceiroNaoEncontrado,
    EmpresaNaoEncontrada,
    ParceiroIndisponivel,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")

# Namespace UUID5 estável — não pode mudar sem invalidar idempotência histórica.
# Gerado de uuid5(uuid.NAMESPACE_URL, "https://fiscalai.com/marketplace/consulta")
_NS_MARKETPLACE: UUID = UUID("9e3e9c7d-cae2-5f8e-9c79-7f5dde4ab2bd")


def _hash_pergunta(empresa_id: UUID, categoria: str, pergunta: str) -> str:
    """Hash SHA-256 hex (64 chars) — base do idempotency_key + auditoria."""
    payload = f"{empresa_id}|{categoria}|{pergunta.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _idempotency_key(
    empresa_id: UUID, categoria: str, pergunta_hash: str, dia: date
) -> UUID:
    """uuid5 estável: mesma pergunta no mesmo dia para a mesma empresa = mesma consulta."""
    nome = f"{empresa_id}|{categoria}|{pergunta_hash}|{dia.isoformat()}"
    return uuid5(_NS_MARKETPLACE, nome)


class ConsultaService:
    async def criar(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        usuario_id: UUID,
        categoria: str,
        pergunta: str,
        consentimento: bool,
        contador_id: UUID | None = None,
        valor_consulta: Decimal | None = None,
    ) -> ConsultaMarketplace:
        if not consentimento:
            raise ConsentimentoAusente(
                "consentimento_compartilhamento=True é obrigatório para criar consulta"
            )

        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        # Pricing — valida categoria fail-fast e calcula SLA/comissão.
        pricing = pricing_para(categoria)
        valor = valor_consulta if valor_consulta is not None else pricing.preco_base
        if valor < pricing.preco_base:
            # Cliente não pode propor abaixo do mínimo do Plano.
            valor = pricing.preco_base
        valor = valor.quantize(Decimal("0.01"))
        comissao_plataforma = comissao(categoria, valor)

        # Contador opcional — quando informado, valida que está apto.
        if contador_id is not None:
            parceiro = await ContadorParceiroRepo(session).por_id(contador_id)
            if parceiro is None:
                raise ContadorParceiroNaoEncontrado(
                    f"Parceiro {contador_id} não encontrado"
                )
            self._validar_parceiro_para_categoria(parceiro, categoria, empresa.uf)
            status_inicial = "atribuida"
        else:
            status_inicial = "aberta"

        agora = datetime.now(tz=_TZ_BR)
        dia_brt = agora.date()
        pergunta_hash = _hash_pergunta(empresa_id, categoria, pergunta)
        idem_key = _idempotency_key(empresa_id, categoria, pergunta_hash, dia_brt)

        values = dict(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            contador_id=contador_id,
            categoria=categoria,
            pergunta=pergunta.strip(),
            pergunta_hash=pergunta_hash,
            contexto_empresa_jsonb=snapshot_empresa(empresa),
            snapshot_versao=SNAPSHOT_VERSAO,
            consentimento_compartilhamento=True,
            status=status_inicial,
            valor_consulta=valor,
            comissao_plataforma=comissao_plataforma,
            idempotency_key=idem_key,
            sla_aceitar_ate=agora + pricing.sla_aceitar,
            sla_responder_ate=agora + pricing.sla_responder,
        )

        consulta = await ConsultaRepo(session).inserir_idempotente(values)
        await session.commit()
        await session.refresh(consulta)

        log.info(
            "marketplace.consulta.criada",
            consulta_id=str(consulta.id),
            empresa_id=str(empresa_id),
            categoria=categoria,
            status=consulta.status,
            valor=str(consulta.valor_consulta),
            idempotency_key=str(idem_key),
        )
        return consulta

    @staticmethod
    def _validar_parceiro_para_categoria(
        parceiro: ContadorParceiro, categoria: str, uf: str | None
    ) -> None:
        if not parceiro.ativo:
            raise ParceiroIndisponivel(
                f"Parceiro {parceiro.id} não está ativo (curadoria)"
            )
        if parceiro.crc_status != "ativo":
            raise ParceiroIndisponivel(
                f"Parceiro {parceiro.id} com CRC {parceiro.crc_status}"
            )
        especialidade = especialidade_para(categoria)
        if especialidade not in parceiro.especialidades:
            raise ParceiroIndisponivel(
                f"Parceiro {parceiro.id} não tem a especialidade '{especialidade}' "
                f"requerida pela categoria '{categoria}'"
            )
        if (
            uf is not None
            and parceiro.uf_atuacao is not None
            and uf not in parceiro.uf_atuacao
        ):
            raise ParceiroIndisponivel(
                f"Parceiro {parceiro.id} não atua em {uf}"
            )

    async def aceitar(
        self,
        session: AsyncSession,
        *,
        consulta_id: UUID,
        contador_id: UUID,
    ) -> ConsultaMarketplace:
        # PR2 stub: setamos a GUC do parceiro para que a policy
        # ``consulta_mkt_parceiro`` libere a leitura. PR3 vai mover isso
        # para o dep do endpoint quando houver auth do parceiro.
        await set_contador_id(session, contador_id)
        consulta = await self._carregar(session, consulta_id)
        if consulta.contador_id != contador_id:
            raise ConsultaForaDeFluxo(
                f"Consulta {consulta_id} não está atribuída a este contador"
            )
        if consulta.status != "atribuida":
            raise ConsultaForaDeFluxo(
                f"Consulta em status {consulta.status!r} não pode ser aceita"
            )
        agora = datetime.now(tz=_TZ_BR)
        if agora > consulta.sla_aceitar_ate:
            raise ConsultaSlaExpirado(
                f"SLA de aceitação venceu em {consulta.sla_aceitar_ate.isoformat()}"
            )
        consulta.status = "aceita"
        consulta.aceita_em = agora
        await session.commit()
        await session.refresh(consulta)
        log.info(
            "marketplace.consulta.aceita",
            consulta_id=str(consulta.id),
            contador_id=str(contador_id),
        )
        return consulta

    async def responder(
        self,
        session: AsyncSession,
        *,
        consulta_id: UUID,
        contador_id: UUID,
        resposta_resumo: str,
        arquivos_anexos: list[dict[str, object]] | None = None,
    ) -> ConsultaMarketplace:
        await set_contador_id(session, contador_id)
        consulta = await self._carregar(session, consulta_id)
        if consulta.contador_id != contador_id:
            raise ConsultaForaDeFluxo(
                f"Consulta {consulta_id} não está atribuída a este contador"
            )
        if consulta.status not in ("aceita", "em_andamento"):
            raise ConsultaForaDeFluxo(
                f"Consulta em status {consulta.status!r} não pode ser respondida"
            )
        agora = datetime.now(tz=_TZ_BR)
        if agora > consulta.sla_responder_ate:
            raise ConsultaSlaExpirado(
                f"SLA de resposta venceu em {consulta.sla_responder_ate.isoformat()}"
            )
        consulta.status = "concluida"
        consulta.resposta_resumo = resposta_resumo
        if arquivos_anexos is not None:
            # JSONB list — caller passa lista de objetos {nome, url, tipo}.
            consulta.arquivos_anexos = {"itens": arquivos_anexos}
        consulta.respondida_em = agora
        await session.commit()
        await session.refresh(consulta)
        log.info(
            "marketplace.consulta.respondida",
            consulta_id=str(consulta.id),
            contador_id=str(contador_id),
            anexos=len(arquivos_anexos) if arquivos_anexos else 0,
        )
        return consulta

    async def avaliar(
        self,
        session: AsyncSession,
        *,
        consulta_id: UUID,
        rating: int,
        comentario: str | None = None,
    ) -> ConsultaMarketplace:
        if rating < 1 or rating > 5:
            raise ConsultaForaDeFluxo("rating deve estar entre 1 e 5")
        consulta = await self._carregar(session, consulta_id)
        if consulta.status != "concluida":
            raise ConsultaForaDeFluxo(
                f"Consulta em status {consulta.status!r} ainda não pode ser avaliada"
            )
        if consulta.rating_cliente is not None:
            raise ConsultaJaAvaliada(
                f"Consulta {consulta_id} já foi avaliada (rating={consulta.rating_cliente})"
            )
        consulta.rating_cliente = rating
        consulta.comentario_cliente = comentario

        # Recalcula rating médio do parceiro com as últimas 10 avaliações
        # (incluindo a recém-aplicada). total_consultas incrementa só agora —
        # consulta é "concluida e avaliada" como métrica de produção.
        if consulta.contador_id is not None:
            await self._recalcular_rating_parceiro(session, consulta.contador_id)
        await session.commit()
        await session.refresh(consulta)
        log.info(
            "marketplace.consulta.avaliada",
            consulta_id=str(consulta.id),
            rating=rating,
        )
        return consulta

    async def _carregar(
        self, session: AsyncSession, consulta_id: UUID
    ) -> ConsultaMarketplace:
        consulta = await ConsultaRepo(session).por_id(consulta_id)
        if consulta is None:
            raise ConsultaNaoEncontrada(
                f"Consulta {consulta_id} não encontrada (ou fora do escopo RLS)"
            )
        return consulta

    @staticmethod
    async def _recalcular_rating_parceiro(
        session: AsyncSession, contador_id: UUID
    ) -> None:
        parceiro = await ContadorParceiroRepo(session).por_id(contador_id)
        if parceiro is None:
            return  # silent — parceiro pode ter sido removido entre passos
        ratings = await ConsultaRepo(session).avaliacoes_recentes(contador_id, limite=10)
        parceiro.total_consultas = (parceiro.total_consultas or 0) + 1
        if ratings:
            media = sum(ratings) / len(ratings)
            parceiro.rating_medio = Decimal(str(round(media, 2)))
