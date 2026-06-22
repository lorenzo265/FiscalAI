"""Service de declarações anuais SN/MEI (Sprint 6 PR3).

Pipeline:
  1. Carrega ApuracaoFiscal mensais do ano (tipo='das') consolidando receitas.
  2. Constrói payload determinístico via gerar_defis / gerar_dasn_simei.
  3. Persiste em ``declaracao_anual`` (UNIQUE por empresa+tipo+ano evita duplicar).
  4. Transmissão é separada — o usuário precisa revisar antes de enviar
     (§8.12: transmissão é ato consciente do cliente).

Restrições por regime:
  DEFIS       — exige empresa SN (regime_tributario='simples_nacional').
  DASN-SIMEI  — exige empresa MEI (regime_tributario='mei').
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.declaracao_anual.gerar_dasn_simei import (
    DadosDasnSimei,
    gerar_dasn_simei,
)
from app.modules.declaracao_anual.gerar_defis import (
    ApuracaoMensalSN,
    DadosSocioeconomicos,
    SocioDefis,
    gerar_defis,
)
from app.modules.declaracao_anual.repo import DeclaracaoAnualRepo
from app.modules.declaracao_anual.schemas import (
    DeclaracaoAnualOut,
    DeclaracaoStatus,
    GerarDasnSimeiIn,
    GerarDefisIn,
    TipoDeclaracao,
    TransmitirOut,
)
from app.modules.empresa.repo import EmpresaRepo
from app.modules.fiscal.repo import ApuracaoFiscalRepo
from app.shared.db.models import ApuracaoFiscal
from app.shared.exceptions import (
    ApuracaoJaExiste,
    EmpresaNaoEncontrada,
    RegimeIncompativel,
    SerproErro,
    SerproTimeout,
)
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)


class _ClienteDecl(Protocol):
    async def transmitir_defis(
        self,
        *,
        cnpj: str,
        ano_base: int,
        dados_declaracao: JsonObject,
        idempotency_key: str,
    ) -> JsonObject: ...

    async def transmitir_dasn_simei(
        self,
        *,
        cnpj: str,
        ano_base: int,
        dados_declaracao: JsonObject,
        idempotency_key: str,
    ) -> JsonObject: ...


class DeclaracaoAnualService:
    # ── DEFIS ────────────────────────────────────────────────────────────────

    async def gerar_defis(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: GerarDefisIn,
    ) -> DeclaracaoAnualOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if empresa.regime_tributario != "simples_nacional":
            raise RegimeIncompativel(
                "DEFIS é exclusivo do Simples Nacional; empresa tem regime "
                f"'{empresa.regime_tributario}'"
            )

        repo = DeclaracaoAnualRepo(session)
        existente = await repo.buscar(empresa_id, TipoDeclaracao.DEFIS.value, payload.ano_base)
        if existente is not None:
            raise ApuracaoJaExiste(
                f"DEFIS de {payload.ano_base} já gerada para empresa {empresa_id}"
            )

        apuracoes_db = await self._listar_apuracoes_das_do_ano(
            session, empresa_id, payload.ano_base
        )
        apuracoes = tuple(_apuracao_db_para_dataclass(a) for a in apuracoes_db)

        socioeconomicos = DadosSocioeconomicos(
            ganho_capital_anual=payload.ganho_capital_anual,
            lucro_contabil_anual=payload.lucro_contabil_anual,
            estoque_inicial=payload.estoque_inicial,
            estoque_final=payload.estoque_final,
            saldo_caixa_inicial=payload.saldo_caixa_inicial,
            saldo_caixa_final=payload.saldo_caixa_final,
            despesa_total_anual=payload.despesa_total_anual,
            isencao_iss_anual=payload.isencao_iss_anual,
            teve_funcionario=payload.teve_funcionario,
            socios=tuple(
                SocioDefis(
                    cpf=s.cpf,
                    nome=s.nome,
                    percentual_capital=s.percentual_capital,
                    rendimentos_isentos=s.rendimentos_isentos,
                    rendimentos_tributaveis=s.rendimentos_tributaveis,
                    pro_labore_anual=s.pro_labore_anual,
                )
                for s in payload.socios
            ),
        )

        resultado = gerar_defis(empresa.cnpj, payload.ano_base, apuracoes, socioeconomicos)

        idempotency_key = _idempotency_key(
            empresa_id, TipoDeclaracao.DEFIS.value, payload.ano_base
        )

        decl = await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=TipoDeclaracao.DEFIS.value,
            ano_base=payload.ano_base,
            payload_json=resultado.payload,
            algoritmo_versao=resultado.algoritmo_versao,
            idempotency_key=idempotency_key,
        )
        await session.commit()

        aviso = None
        if resultado.meses_apurados < 12:
            aviso = (
                f"Apenas {resultado.meses_apurados} mês(es) de apuração no "
                f"ano {payload.ano_base}. Revise antes de transmitir."
            )

        log.info(
            "defis.gerada",
            empresa_id=str(empresa_id),
            ano_base=payload.ano_base,
            receita_bruta=str(resultado.receita_bruta_anual),
            meses=resultado.meses_apurados,
        )

        return DeclaracaoAnualOut(
            id=decl.id,
            empresa_id=decl.empresa_id,
            tipo=TipoDeclaracao.DEFIS,
            ano_base=decl.ano_base,
            status=DeclaracaoStatus.GERADA,
            protocolo=None,
            transmitida_em=None,
            receita_bruta_anual=resultado.receita_bruta_anual,
            aviso=aviso,
        )

    # ── DASN-SIMEI ───────────────────────────────────────────────────────────

    async def gerar_dasn_simei(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: GerarDasnSimeiIn,
    ) -> DeclaracaoAnualOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if empresa.regime_tributario != "mei":
            raise RegimeIncompativel(
                "DASN-SIMEI é exclusivo do MEI; empresa tem regime "
                f"'{empresa.regime_tributario}'"
            )

        repo = DeclaracaoAnualRepo(session)
        existente = await repo.buscar(
            empresa_id, TipoDeclaracao.DASN_SIMEI.value, payload.ano_base
        )
        if existente is not None:
            raise ApuracaoJaExiste(
                f"DASN-SIMEI de {payload.ano_base} já gerada para empresa {empresa_id}"
            )

        dados = DadosDasnSimei(
            receita_comercio_industria=payload.receita_comercio_industria,
            receita_servicos=payload.receita_servicos,
            teve_empregado=payload.teve_empregado,
            eh_caminhoneiro=payload.eh_caminhoneiro,
        )
        resultado = gerar_dasn_simei(empresa.cnpj, payload.ano_base, dados)

        idempotency_key = _idempotency_key(
            empresa_id, TipoDeclaracao.DASN_SIMEI.value, payload.ano_base
        )

        decl = await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=TipoDeclaracao.DASN_SIMEI.value,
            ano_base=payload.ano_base,
            payload_json=resultado.payload,
            algoritmo_versao=resultado.algoritmo_versao,
            idempotency_key=idempotency_key,
        )
        await session.commit()

        aviso = (
            "Receita bruta excedeu o limite do MEI — empresa pode ter sido "
            "desenquadrada. Confirme com sua contabilidade."
            if resultado.excedeu_limite_mei
            else None
        )

        log.info(
            "dasn_simei.gerada",
            empresa_id=str(empresa_id),
            ano_base=payload.ano_base,
            receita_bruta=str(resultado.receita_bruta_anual),
            excedeu=resultado.excedeu_limite_mei,
        )

        return DeclaracaoAnualOut(
            id=decl.id,
            empresa_id=decl.empresa_id,
            tipo=TipoDeclaracao.DASN_SIMEI,
            ano_base=decl.ano_base,
            status=DeclaracaoStatus.GERADA,
            protocolo=None,
            transmitida_em=None,
            receita_bruta_anual=resultado.receita_bruta_anual,
            aviso=aviso,
        )

    # ── transmissão ──────────────────────────────────────────────────────────

    async def transmitir(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        declaracao_id: UUID,
        *,
        serpro_client: _ClienteDecl | None,
    ) -> TransmitirOut:
        repo = DeclaracaoAnualRepo(session)
        decl = await repo.por_id(declaracao_id)
        if decl is None or decl.empresa_id != empresa_id:
            raise EmpresaNaoEncontrada(
                f"Declaração {declaracao_id} não encontrada para empresa {empresa_id}"
            )

        if decl.status == "transmitida":
            return TransmitirOut(
                declaracao_id=decl.id,
                tipo=TipoDeclaracao(decl.tipo),
                status=DeclaracaoStatus.TRANSMITIDA,
                protocolo=decl.protocolo,
                mensagem="Declaração já transmitida (idempotente).",
            )

        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if serpro_client is None:
            await repo.marcar_erro(
                decl.id,
                erro_codigo="SerproIndisponivel",
                erro_mensagem="SerproClient não disponível",
            )
            await session.commit()
            return TransmitirOut(
                declaracao_id=decl.id,
                tipo=TipoDeclaracao(decl.tipo),
                status=DeclaracaoStatus.ERRO,
                protocolo=None,
                mensagem="SERPRO offline. Tente novamente.",
                erro="SerproIndisponivel",
            )

        try:
            if decl.tipo == TipoDeclaracao.DEFIS.value:
                resposta = await serpro_client.transmitir_defis(
                    cnpj=empresa.cnpj,
                    ano_base=decl.ano_base,
                    dados_declaracao=decl.payload_json,
                    idempotency_key=decl.idempotency_key,
                )
            else:
                resposta = await serpro_client.transmitir_dasn_simei(
                    cnpj=empresa.cnpj,
                    ano_base=decl.ano_base,
                    dados_declaracao=decl.payload_json,
                    idempotency_key=decl.idempotency_key,
                )
        except (SerproErro, SerproTimeout) as exc:
            await repo.marcar_erro(
                decl.id, erro_codigo=exc.codigo, erro_mensagem=exc.mensagem
            )
            await session.commit()
            log.warning(
                "declaracao_anual.transmissao.erro",
                declaracao_id=str(decl.id),
                tipo=decl.tipo,
                erro=exc.codigo,
            )
            return TransmitirOut(
                declaracao_id=decl.id,
                tipo=TipoDeclaracao(decl.tipo),
                status=DeclaracaoStatus.ERRO,
                protocolo=None,
                mensagem="Falha ao transmitir ao SERPRO.",
                erro=exc.codigo,
            )

        protocolo, recibo_key = _extrair_protocolo(resposta, decl.tipo)
        await repo.marcar_transmitida(
            decl.id, protocolo=protocolo, recibo_pdf_storage_key=recibo_key
        )
        await session.commit()

        log.info(
            "declaracao_anual.transmissao.ok",
            declaracao_id=str(decl.id),
            tipo=decl.tipo,
            protocolo=protocolo,
        )

        return TransmitirOut(
            declaracao_id=decl.id,
            tipo=TipoDeclaracao(decl.tipo),
            status=DeclaracaoStatus.TRANSMITIDA,
            protocolo=protocolo,
            mensagem=f"{decl.tipo} transmitida com sucesso.",
        )

    # ── helpers internos ─────────────────────────────────────────────────────

    async def _listar_apuracoes_das_do_ano(
        self, session: AsyncSession, empresa_id: UUID, ano: int
    ) -> list[ApuracaoFiscal]:
        rows = await ApuracaoFiscalRepo(session).listar_empresa(empresa_id, tipo="das")
        return [r for r in rows if r.competencia.year == ano]


# ── helpers puros ────────────────────────────────────────────────────────────


def _idempotency_key(empresa_id: UUID, tipo: str, ano: int) -> str:
    base = f"{tipo.lower()}:{empresa_id}:{ano}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, base))


def _apuracao_db_para_dataclass(a: ApuracaoFiscal) -> ApuracaoMensalSN:
    from decimal import Decimal

    output = a.output_jsonb or {}
    competencia: date = a.competencia
    return ApuracaoMensalSN(
        competencia=f"{competencia.year:04d}-{competencia.month:02d}",
        receita_mes=Decimal(str(output.get("receita_mes", "0"))),
        valor_das=Decimal(str(output.get("valor_das", "0"))),
        anexo=str(output.get("anexo") or "I"),
        anexo_efetivo=str(output.get("anexo_efetivo") or output.get("anexo") or "I"),
    )


def _extrair_protocolo(
    resposta: JsonObject, tipo: str
) -> tuple[str | None, str | None]:
    dados_raw = resposta.get("dados")
    if isinstance(dados_raw, dict):
        dados = dados_raw
    elif isinstance(dados_raw, str):
        try:
            import json

            dados = json.loads(dados_raw)
        except (ValueError, TypeError):
            dados = {}
    else:
        dados = {}

    protocolo = (
        dados.get("numeroDeclaracao")
        or dados.get("protocolo")
        or resposta.get("numeroDeclaracao")
    )
    recibo_b64 = dados.get("recibo") or resposta.get("recibo")
    recibo_key = (
        f"{tipo.lower()}/{protocolo}.pdf" if recibo_b64 and protocolo else None
    )
    return (str(protocolo) if protocolo else None, recibo_key)
