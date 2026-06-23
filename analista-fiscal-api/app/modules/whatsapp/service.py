from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.whatsapp.handlers import classificar_intent, resposta_para_intent
from app.modules.whatsapp.repo import MensagemProcessadaRepo, SessaoWhatsAppRepo
from app.modules.whatsapp.schemas import MensagemRecebidaIn, RespostaWhatsApp

log = structlog.get_logger(__name__)


class WhatsAppService:
    async def processar_mensagem(
        self,
        session: AsyncSession,
        msg: MensagemRecebidaIn,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        sender: Any | None = None,
    ) -> RespostaWhatsApp | None:
        """Processa uma mensagem recebida e envia resposta.

        Retorna RespostaWhatsApp se uma resposta foi gerada, None se ignorado
        (ex.: mensagem não-texto, dedup).

        Fluxo:
          1. Carrega / cria sessão de conversa
          2. Classifica intent (Camada 1 determinística)
          3. Gera texto de resposta
          4. Envia via sender (Meta Cloud API)
          5. Incrementa contador de mensagens da sessão
        """
        if msg.tipo != "text" or not msg.texto:
            log.info("whatsapp.msg.ignorada", tipo=msg.tipo, phone_sufixo=msg.phone[-4:])
            return None

        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            log.warning("whatsapp.empresa_nao_encontrada", empresa_id=str(empresa_id))
            return None

        # §8.9 — dedup atômico ANTES de qualquer side-effect. Meta retry sob 5xx/timeout.
        if msg.mensagem_id:
            dedup_repo = MensagemProcessadaRepo(session)
            registrou = await dedup_repo.marcar_processada(
                mensagem_id=msg.mensagem_id,
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                phone=msg.phone,
            )
            if not registrou:
                log.info(
                    "whatsapp.msg.duplicada",
                    mensagem_id=msg.mensagem_id,
                    phone_sufixo=msg.phone[-4:],
                )
                await session.commit()
                return None

        repo = SessaoWhatsAppRepo(session)
        sessao = await repo.obter_ou_criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            phone=msg.phone,
        )

        intent = classificar_intent(msg.texto)
        texto_resposta, tipo_resposta = resposta_para_intent(
            intent, sessao.mensagens_na_sessao
        )

        await repo.incrementar_mensagens(sessao)
        await session.commit()

        log.info(
            "whatsapp.msg.processada",
            phone_sufixo=msg.phone[-4:],
            intent=intent,
            tipo_resposta=tipo_resposta,
            mensagens_total=sessao.mensagens_na_sessao,
        )

        resposta = RespostaWhatsApp(
            phone=msg.phone,
            texto=texto_resposta,
            tipo=tipo_resposta,
        )

        if sender is not None:
            try:
                await sender.enviar_texto(msg.phone, texto_resposta)
            except Exception as exc:
                log.error("whatsapp.send.falhou", erro=str(exc), phone_sufixo=msg.phone[-4:])

        return resposta

    async def encontrar_empresa_por_phone(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        phone: str,
    ) -> UUID | None:
        """Tenta encontrar empresa associada ao número WhatsApp."""
        from sqlalchemy import select

        from app.shared.db.models import Empresa

        stmt = select(Empresa.id).where(
            Empresa.tenant_id == tenant_id,
            Empresa.whatsapp_phone == phone,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UUID(str(row))
