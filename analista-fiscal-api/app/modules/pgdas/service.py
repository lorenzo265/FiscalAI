"""Service de transmissão PGDAS-D ao SERPRO Integra Contador.

Pipeline:
  1. Carrega ApuracaoFiscal (tipo='das') já calculada na Sprint 2.
  2. Monta payload SERPRO a partir de `apuracao.output_jsonb` + dados da
     empresa (CNPJ, regime SN, anexo).
  3. Cria TransmissaoPgdas em status='pendente' com idempotency_key
     determinístico.
  4. Chama SerproClient.transmitir_pgdas_d. Em sucesso, salva protocolo,
     atualiza `apuracao.transmitido_em` e `status='transmitida'`.
  5. Em erro, marca transmissão como 'erro' com codigo + mensagem.

Retificação cria nova linha com `tentativa=N+1` e `eh_retificadora=True`,
mantendo o histórico imutável (§8.2).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Protocol

from app.shared.db.models import ApuracaoFiscal, Empresa
from app.shared.types import JsonObject
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.fiscal.repo import ApuracaoFiscalRepo
from app.modules.pgdas.repo import TransmissoesPgdasRepo
from app.modules.pgdas.schemas import (
    TransmissaoStatus,
    TransmitirPgdasOut,
)
from app.shared.exceptions import (
    ApuracaoNaoEncontrada,
    EmpresaNaoEncontrada,
    RegimeIncompativel,
    SerproErro,
    SerproTimeout,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_REGIME_SN = "simples_nacional"


class _ClientePgdas(Protocol):
    async def transmitir_pgdas_d(
        self,
        *,
        cnpj: str,
        periodo_apuracao: str,
        dados_declaracao: JsonObject,
        idempotency_key: str,
    ) -> JsonObject: ...


class PgdasService:
    async def transmitir(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        competencia: date,
        *,
        eh_retificadora: bool,
        serpro_client: _ClientePgdas | None,
    ) -> TransmitirPgdasOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if empresa.regime_tributario != _REGIME_SN:
            raise RegimeIncompativel(
                "PGDAS-D é exclusivo do Simples Nacional; empresa tem regime "
                f"'{empresa.regime_tributario}'"
            )

        apuracao = await ApuracaoFiscalRepo(session).buscar(
            empresa_id, competencia, "das"
        )
        if apuracao is None:
            raise ApuracaoNaoEncontrada(
                f"DAS de {competencia:%Y-%m} ainda não calculado — calcule antes "
                "de transmitir"
            )

        repo = TransmissoesPgdasRepo(session)
        if eh_retificadora:
            ultima = await repo.ultima_transmissao(empresa_id, competencia)
            if ultima is None or ultima.status != "transmitida":
                raise RegimeIncompativel(
                    "Retificação requer transmissão original bem-sucedida."
                )

        tentativa = await repo.proxima_tentativa(empresa_id, competencia)
        idempotency_key = _gerar_idempotency_key(
            empresa_id, competencia, tentativa, eh_retificadora
        )
        payload_dados = _montar_payload_declaracao(empresa, apuracao)
        periodo = _competencia_para_aaaa_mm(competencia)

        transmissao = await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            apuracao_id=apuracao.id,
            competencia=competencia,
            tentativa=tentativa,
            eh_retificadora=eh_retificadora,
            idempotency_key=idempotency_key,
            payload_envio_json={
                "periodoApuracao": periodo,
                **payload_dados,
            },
        )

        if serpro_client is None:
            await repo.marcar_erro(
                transmissao.id,
                erro_codigo="SerproIndisponivel",
                erro_mensagem="SerproClient não inicializado em runtime",
            )
            await session.commit()
            return TransmitirPgdasOut(
                transmissao_id=transmissao.id,
                apuracao_id=apuracao.id,
                competencia=competencia,
                tentativa=tentativa,
                eh_retificadora=eh_retificadora,
                status=TransmissaoStatus.ERRO,
                protocolo=None,
                mensagem="Transmissão registrada mas não enviada (SERPRO offline).",
                erro="SerproIndisponivel",
            )

        try:
            resposta = await serpro_client.transmitir_pgdas_d(
                cnpj=empresa.cnpj,
                periodo_apuracao=periodo,
                dados_declaracao=payload_dados,
                idempotency_key=idempotency_key,
            )
        except (SerproErro, SerproTimeout) as exc:
            await repo.marcar_erro(
                transmissao.id,
                erro_codigo=exc.codigo,
                erro_mensagem=exc.mensagem,
            )
            await session.commit()
            log.warning(
                "pgdas.transmissao.erro",
                empresa_id=str(empresa_id),
                competencia=competencia.isoformat(),
                erro=exc.codigo,
            )
            return TransmitirPgdasOut(
                transmissao_id=transmissao.id,
                apuracao_id=apuracao.id,
                competencia=competencia,
                tentativa=tentativa,
                eh_retificadora=eh_retificadora,
                status=TransmissaoStatus.ERRO,
                protocolo=None,
                mensagem="Falha ao transmitir ao SERPRO.",
                erro=exc.codigo,
            )

        protocolo, recibo_pdf = _extrair_protocolo_e_recibo(resposta)
        await repo.marcar_sucesso(
            transmissao.id,
            protocolo=protocolo,
            resposta_json=resposta,
            recibo_pdf_storage_key=recibo_pdf,
        )
        # Marca apuracao como transmitida (Sprint 2 já tem o campo).
        apuracao.transmitido_em = datetime.now(_TZ_BR)
        apuracao.status = "transmitida"
        await session.commit()

        log.info(
            "pgdas.transmissao.ok",
            empresa_id=str(empresa_id),
            competencia=competencia.isoformat(),
            tentativa=tentativa,
            eh_retificadora=eh_retificadora,
            protocolo=protocolo,
        )

        return TransmitirPgdasOut(
            transmissao_id=transmissao.id,
            apuracao_id=apuracao.id,
            competencia=competencia,
            tentativa=tentativa,
            eh_retificadora=eh_retificadora,
            status=TransmissaoStatus.TRANSMITIDA,
            protocolo=protocolo,
            mensagem="PGDAS-D transmitido com sucesso.",
        )


# ── helpers puros (sem I/O) ──────────────────────────────────────────────────


def _competencia_para_aaaa_mm(competencia: date) -> str:
    return f"{competencia.year:04d}{competencia.month:02d}"


def _gerar_idempotency_key(
    empresa_id: uuid.UUID,
    competencia: date,
    tentativa: int,
    eh_retificadora: bool,
) -> str:
    """Determinístico — retentativas no mesmo (empresa, comp, tentativa) batem
    no lock do SERPRO. Retificadora muda o sufixo para gerar nova chave.
    """
    sufixo = "ret" if eh_retificadora else "ori"
    base = f"pgdas:{empresa_id}:{competencia.isoformat()}:{tentativa}:{sufixo}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, base))


def _montar_payload_declaracao(empresa: Empresa, apuracao: ApuracaoFiscal) -> JsonObject:
    """Constrói o subobjeto `dados` enviado ao SERPRO (PGDAS-D).

    Para o MVP cobrimos o ramo unicidade: 1 estabelecimento (a própria empresa),
    receita do mês = `output_jsonb.receita_mes`. Receitas por estabelecimento /
    deduções / regimes especiais (substituição tributária, retenção ISS,
    imunidade) são extensões futuras (PR3).
    """
    output = apuracao.output_jsonb or {}
    receita_mes = output.get("receita_mes", "0")
    anexo_efetivo = output.get("anexo_efetivo") or output.get("anexo") or "I"

    estabelecimento = {
        "cnpjCompleto": empresa.cnpj,
        "atividades": [
            {
                "idAtividade": _id_atividade_por_anexo(anexo_efetivo),
                "valorAtividade": str(receita_mes),
                "receitasAtividade": [
                    {
                        "valor": str(receita_mes),
                        "municipio": (empresa.municipio or ""),
                        "uf": (empresa.uf or ""),
                        "isencoes": [],
                        "reducoes": [],
                        "qualificacoesTributarias": [],
                        "exigibilidadesSuspensas": [],
                    }
                ],
            }
        ],
        "folhasSalario": [],
        "naoOptante": False,
    }

    return {
        "declaracao": {
            "tipoDeclaracao": 1,  # 1=Original; service detecta retificadora antes
            "receitaPaCompetencia": str(receita_mes),
            "receitaPaCaixa": str(receita_mes),
            "valorFixoIcms": "0",
            "valorFixoIss": "0",
            "estabelecimentos": [estabelecimento],
            "folhasSalario": [],
            "naoOptante": False,
            "transferirReceitaSt": False,
        }
    }


# Mapa anexo → idAtividade do PGDAS-D (Manual SERPRO v1.0).
_ID_ATIVIDADE_POR_ANEXO: dict[str, int] = {
    "I": 1,  # Comércio
    "II": 2,  # Indústria
    "III": 3,  # Serviços Anexo III
    "IV": 4,  # Serviços Anexo IV
    "V": 5,  # Serviços Anexo V
}


def _id_atividade_por_anexo(anexo: str) -> int:
    return _ID_ATIVIDADE_POR_ANEXO.get(anexo, 1)


def _extrair_protocolo_e_recibo(
    resposta: JsonObject,
) -> tuple[str | None, str | None]:
    """Decodifica `protocolo` (numeroDeclaracao) e chave do recibo PDF."""
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
    # SERPRO envia o recibo em base64 no campo `recibo` — no MVP só registramos
    # a presença; persistência S3 fica como integração de infra.
    recibo_b64 = dados.get("recibo") or resposta.get("recibo")
    recibo_key = f"pgdas/{protocolo}.pdf" if recibo_b64 and protocolo else None

    return (str(protocolo) if protocolo else None, recibo_key)
