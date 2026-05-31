"""AlertaAdminService — orquestrador da Camada 2 (Sprint 19.5 PR2).

Três responsabilidades:

  1. **Varredura periódica** (chamada pelo worker Celery):
     ``verificar_e_alertar(hoje)`` consulta os 7 tipos de tabela SCD via
     ``SCDTabelasRepo`` e gera alertas idempotentes para cada caso que
     `avaliacao_vigencias.avaliar_*` reportar como crítico/aviso/info.

  2. **Resolução automática** (chamada por ``TabelaAdminService`` após
     POST da Camada 1 PR1): ``resolver_relacionados(tipo_tabela, ano)``
     marca alertas abertos do mesmo tipo+ano como ``resolvido_em=now()``.

  3. **Hook digest admin** (chamado opcionalmente pelo gerador de digest
     WhatsApp existente): ``alertas_para_digest_admin()`` devolve um
     bullet markdown dos alertas críticos abertos, pronto para concatenar
     no digest do contador admin do sistema (não da PME).

Todas as operações usam a mesma sessão admin (``tax_table_admin``) — o
service é instanciado pelo worker e pelo router PR1.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tabelas_admin.alertas_repo import AlertaAdminRepo
from app.modules.tabelas_admin.avaliacao_vigencias import (
    ResultadoAvaliacao,
    avaliar_cbs_ibs,
    avaliar_fgts,
    avaliar_icms_uf,
    avaliar_inss_irrf,
    avaliar_presuncao_lp,
    avaliar_simples_nacional,
)
from app.modules.tabelas_admin.repo import SCDTabelasRepo
from app.shared.db.models import AlertaAdmin

if TYPE_CHECKING:
    from app.modules.tabelas_admin.alertas_schemas import Severidade

log = structlog.get_logger(__name__)


class AlertaAdminService:
    def __init__(
        self,
        *,
        alerta_repo: AlertaAdminRepo,
        scd_repo: SCDTabelasRepo,
    ) -> None:
        self._alerta_repo = alerta_repo
        self._scd_repo = scd_repo

    # ── Varredura (worker Celery) ──────────────────────────────────────

    async def verificar_e_alertar(
        self, session: AsyncSession, hoje: date
    ) -> tuple[int, int]:
        """Roda os 7 avaliadores. Devolve (criados, ja_existiam).

        Não falha se um tipo errar — loga e segue para o próximo. O worker
        é resiliente por design (defesa em profundidade contra DB com seed
        incompleto em algum tipo isolado).
        """
        criados = 0
        ja_existiam = 0

        async def _processa(
            resultado: ResultadoAvaliacao,
        ) -> None:
            nonlocal criados, ja_existiam
            if not resultado.deve_alertar:
                return
            tipo_tabela = str(resultado.contexto.get("tipo_tabela", "?"))
            ano_raw = resultado.contexto.get("ano_corrente", hoje.year)
            # ``contexto`` é dict[str, object] no dataclass — coerção defensiva.
            ano = int(ano_raw) if isinstance(ano_raw, (int, str)) else hoje.year
            row = await self._alerta_repo.upsert_idempotente(
                tipo=resultado.tipo,
                tipo_tabela=tipo_tabela,
                ano=ano,
                severidade=resultado.severidade,
                titulo=resultado.titulo,
                descricao=resultado.descricao,
                contexto=resultado.contexto,
            )
            if row is None:
                ja_existiam += 1
                log.debug(
                    "tabelas.verificacao.alerta_ja_existia",
                    tipo_tabela=tipo_tabela,
                    ano=ano,
                )
            else:
                criados += 1
                log.info(
                    "tabelas.verificacao.alerta_criado",
                    alerta_id=str(row.id),
                    tipo=resultado.tipo,
                    severidade=resultado.severidade,
                    tipo_tabela=tipo_tabela,
                    ano=ano,
                )

        # INSS
        try:
            inss = await self._scd_repo.valid_from_ativa_inss(hoje)
            await _processa(
                avaliar_inss_irrf(
                    tipo_tabela="inss",
                    valid_from_ativa=inss,
                    hoje=hoje,
                )
            )
        except Exception:
            log.exception("tabelas.verificacao.tipo_falhou", tipo_tabela="inss")

        # IRRF
        try:
            irrf = await self._scd_repo.valid_from_ativa_irrf(hoje)
            await _processa(
                avaliar_inss_irrf(
                    tipo_tabela="irrf",
                    valid_from_ativa=irrf,
                    hoje=hoje,
                )
            )
        except Exception:
            log.exception("tabelas.verificacao.tipo_falhou", tipo_tabela="irrf")

        # FGTS
        try:
            fgts = await self._scd_repo.valid_from_ativa_fgts(hoje)
            await _processa(
                avaliar_fgts(valid_from_ativa=fgts, hoje=hoje)
            )
        except Exception:
            log.exception("tabelas.verificacao.tipo_falhou", tipo_tabela="fgts")

        # Simples Nacional
        try:
            sn = await self._scd_repo.valid_from_ativa_simples(hoje)
            await _processa(
                avaliar_simples_nacional(valid_from_ativa=sn, hoje=hoje)
            )
        except Exception:
            log.exception(
                "tabelas.verificacao.tipo_falhou", tipo_tabela="simples_nacional"
            )

        # Presunção LP
        try:
            presuncao = await self._scd_repo.valid_from_ativa_presuncao(hoje)
            await _processa(
                avaliar_presuncao_lp(valid_from_ativa=presuncao, hoje=hoje)
            )
        except Exception:
            log.exception(
                "tabelas.verificacao.tipo_falhou", tipo_tabela="presuncao_lp"
            )

        # ICMS UF — 1 alerta por UF afetada.
        try:
            ativos_por_uf = (
                await self._scd_repo.valid_from_ativa_icms_por_uf(hoje)
            )
            from app.modules.tabelas_admin.validadores import _UFS_BRASIL

            for uf in sorted(_UFS_BRASIL):
                vf = ativos_por_uf.get(uf)
                # Empresa pode operar em UFs sem cobertura — não vamos alertar
                # por todas as 27 UFs faltantes (ruído). Só alertamos para UFs
                # que JÁ ESTÃO no SCD (vigência velha).
                if vf is None:
                    continue
                await _processa(
                    avaliar_icms_uf(uf=uf, valid_from_ativa=vf, hoje=hoje)
                )
        except Exception:
            log.exception(
                "tabelas.verificacao.tipo_falhou", tipo_tabela="icms_uf"
            )

        # CBS / IBS
        try:
            cbs_ativa = await self._scd_repo.valid_from_ativa_cbs_ibs(hoje)
            cbs_futura = (
                await self._scd_repo.proxima_vigencia_futura_cbs_ibs(hoje)
            )
            await _processa(
                avaliar_cbs_ibs(
                    valid_from_ativa=cbs_ativa,
                    proxima_vigencia_futura=cbs_futura,
                    hoje=hoje,
                )
            )
        except Exception:
            log.exception(
                "tabelas.verificacao.tipo_falhou", tipo_tabela="cbs_ibs"
            )

        # Commit explícito — o worker chama em sessão dedicada.
        await session.commit()
        log.info(
            "tabelas.verificacao.concluida",
            criados=criados,
            ja_existiam=ja_existiam,
            hoje=hoje.isoformat(),
        )
        return criados, ja_existiam

    # ── Operações pontuais (endpoints) ─────────────────────────────────

    async def listar(
        self,
        *,
        severidade: "Severidade | None" = None,
        resolvido: bool | None = None,
        limite: int = 100,
    ) -> list[AlertaAdmin]:
        return await self._alerta_repo.listar(
            severidade=severidade, resolvido=resolvido, limite=limite
        )

    async def resolver(
        self,
        session: AsyncSession,
        alerta_id: UUID,
        *,
        usuario_id: UUID | None = None,
    ) -> AlertaAdmin | None:
        alerta = await self._alerta_repo.resolver(
            alerta_id, usuario_id=usuario_id
        )
        if alerta is not None:
            await session.commit()
        return alerta

    async def snooze(
        self,
        session: AsyncSession,
        alerta_id: UUID,
        *,
        dias: int,
    ) -> AlertaAdmin | None:
        alerta = await self._alerta_repo.snooze(alerta_id, dias=dias)
        if alerta is not None:
            await session.commit()
        return alerta

    async def resolver_relacionados(
        self,
        session: AsyncSession,
        *,
        tipo_tabela: str,
        ano: int,
    ) -> int:
        """Hook chamado por ``TabelaAdminService`` após POST Camada 1.

        Não comita — o caller (TabelaAdminService._gravar_log) já comita
        a vigência junto. Atomicidade: nova vigência + resolução de
        alertas relacionados na mesma transação.
        """
        return await self._alerta_repo.resolver_relacionados(
            tipo_tabela=tipo_tabela, ano=ano
        )

    # ── Hooks digest WhatsApp admin (Sprint 15.5 + Sprint 19.6 PR3 #42) ──

    async def alertas_para_digest_admin(self) -> list[str]:
        """Devolve bullets markdown dos alertas críticos abertos.

        Hook opcional — chamado pelo gerador de digest se
        ``settings.ADMIN_WHATSAPP_PHONE`` estiver configurado. Lista vazia
        = não inclui seção no digest.
        """
        abertos = await self._alerta_repo.listar(
            severidade="critico", resolvido=False, limite=10
        )
        return [
            f"⚠ *{a.titulo}* — {a.descricao}" for a in abertos
        ]

    async def montar_digest_admin_completo(
        self, *, base_url_painel: str = "https://app.fiscalai.com.br/admin"
    ) -> dict[str, object]:
        """Sprint 19.6 PR3 (#42) — digest admin completo em markdown.

        Devolve ``{texto, alertas_count, alertas_por_severidade}`` com
        texto pronto pra envio via canal externo (Meta WhatsApp utility
        template, e-mail, Slack). Hoje consumido por endpoint
        ``GET /v1/admin/alertas/digest`` — operador admin pode disparar
        via cron + script externo enquanto worker dedicado não existe.

        Estrutura do texto:

            🤖 *FiscalAI — Digest Admin*
            Resumo das tabelas tributárias (`tipo_tabela` SCD)

            *⚠ Alertas críticos (N)*
            • Tabela INSS 2026 não atualizada — Portaria de janeiro/2026...
            • ...

            *📊 Alertas em aberto (resumo)*
            • crítico: N
            • aviso: M
            • info: K

            Painel: {base_url_painel}/tabelas

        Sem alertas críticos = devolve texto curto "✅ Tudo em dia".
        """
        criticos = await self._alerta_repo.listar(
            severidade="critico", resolvido=False, limite=10
        )
        avisos = await self._alerta_repo.listar(
            severidade="aviso", resolvido=False, limite=100
        )
        infos = await self._alerta_repo.listar(
            severidade="info", resolvido=False, limite=100
        )

        contadores: dict[str, int] = {
            "critico": len(criticos),
            "aviso": len(avisos),
            "info": len(infos),
        }
        total = sum(contadores.values())

        if not criticos:
            texto = (
                "🤖 *FiscalAI — Digest Admin*\n"
                "✅ Tudo em dia. Sem alertas críticos do painel admin.\n"
                f"\nAbertos: {total} (sem severidade crítica). "
                f"Painel: {base_url_painel}/tabelas"
            )
        else:
            bullets = "\n".join(
                f"• *{a.titulo}* — {a.descricao}" for a in criticos
            )
            texto = (
                "🤖 *FiscalAI — Digest Admin*\n"
                "Resumo do painel de tabelas tributárias.\n\n"
                f"*⚠ Alertas críticos ({len(criticos)})*\n"
                f"{bullets}\n\n"
                f"*📊 Outros abertos*\n"
                f"• aviso: {contadores['aviso']}\n"
                f"• info: {contadores['info']}\n\n"
                f"Painel: {base_url_painel}/tabelas"
            )
        return {
            "texto": texto,
            "alertas_count": total,
            "alertas_por_severidade": contadores,
        }


__all__ = ["AlertaAdminService"]
