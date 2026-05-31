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
from decimal import Decimal
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
    MunicipioIbgeAusente,
    RegimeIncompativel,
    RetificacaoSemOriginal,
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
        if not empresa.codigo_municipio_ibge:
            raise MunicipioIbgeAusente(
                "Cadastre o código IBGE 7-dígitos do município da empresa antes "
                "de transmitir PGDAS-D. Use PATCH /v1/empresas/{eid}/municipio-ibge."
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
                raise RetificacaoSemOriginal(
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

    v3 (Fase 2 PR8 — MAJOR M2 da auditoria Sprints 4-6): itera
    ``output_jsonb.receitas_por_anexo`` para discriminar atividades — exigência
    real do PGDAS-D quando empresa tem receitas em múltiplos anexos (Anexo I + III,
    ou Fator R alternando III↔V).

    Compatibilidade: apurações pré-v3 (sem ``receitas_por_anexo`` no jsonb)
    caem no fallback ``{anexo_efetivo: receita_mes}`` — comportamento idêntico ao
    PGDAS PR2 original (1 atividade, idAtividade do anexo_efetivo).

    Out-of-scope (pendência consciente):
      * 1 estabelecimento por empresa (a própria) — múltiplas filiais não cobertas.
      * Deduções / substituição tributária / retenção ISS / imunidades — vazias.
    """
    output = apuracao.output_jsonb or {}
    receita_total = Decimal(str(output.get("receita_mes", "0")))
    anexo_efetivo_default = output.get("anexo_efetivo") or output.get("anexo") or "I"

    receitas_raw = output.get("receitas_por_anexo") or {}
    receitas_por_anexo: dict[str, Decimal] = {
        anexo: Decimal(str(valor))
        for anexo, valor in receitas_raw.items()
        if Decimal(str(valor)) > Decimal("0")
    }
    if not receitas_por_anexo:
        # Apuração pré-v3 (sn.das.v2 e anteriores) — fallback compat.
        receitas_por_anexo = {anexo_efetivo_default: receita_total}

    atividades: list[JsonObject] = [
        {
            "idAtividade": _id_atividade_por_anexo(anexo),
            "valorAtividade": _decstr(valor),
            "receitasAtividade": [
                {
                    "valor": _decstr(valor),
                    "municipio": (empresa.codigo_municipio_ibge or ""),
                    "uf": (empresa.uf or ""),
                    "isencoes": [],
                    "reducoes": [],
                    "qualificacoesTributarias": [],
                    "exigibilidadesSuspensas": [],
                }
            ],
        }
        for anexo, valor in sorted(receitas_por_anexo.items())
    ]

    estabelecimento = {
        "cnpjCompleto": empresa.cnpj,
        "atividades": atividades,
        "folhasSalario": [],
        "naoOptante": False,
    }

    return {
        "declaracao": {
            "tipoDeclaracao": 1,  # 1=Original; service detecta retificadora antes
            "receitaPaCompetencia": _decstr(receita_total),
            "receitaPaCaixa": _decstr(receita_total),
            "valorFixoIcms": "0",
            "valorFixoIss": "0",
            "estabelecimentos": [estabelecimento],
            "folhasSalario": [],
            "naoOptante": False,
            "transferirReceitaSt": False,
        }
    }


def _decstr(v: Decimal) -> str:
    """Serializa Decimal preservando 2 casas — formato esperado pelo SERPRO."""
    return f"{v.quantize(Decimal('0.01')):.2f}"


# Mapa anexo → idAtividade do PGDAS-D — Manual SERPRO v1.4+ (2022+).
#
# Sprint 19.6 PR2 (#16): corrige mapa anterior que seguia Manual v1.0
# (I→1, II→2, III→3, IV→4, V→5). SERPRO rejeitaria o payload em prod
# real (ID 3 hoje é "locação de bens móveis", não serviços ISS Anexo
# III; ID 5 hoje é Anexo IV; ID 6 é Anexo V — IDs deslocados).
#
# Códigos do Manual v1.4+:
#   1 — Revenda de mercadorias                     (Anexo I)
#   2 — Venda de mercadorias industrializadas      (Anexo II)
#   3 — Locação de bens móveis                     (subtipo do Anexo III)
#   4 — Prestação de serviços (art. 18 §1º LC 123) (Anexo III ISS — caso comum)
#   5 — Prestação de serviços do §5º-C art. 18     (Anexo IV — construção civil)
#   6 — Prestação de serviços do §5º-D/Anexo V     (Anexo V — serviços técnicos)
#   7 — Atividades com tributação concentrada/ST   (raro — out-of-scope MVP)
#   8 — Exportação de mercadorias ou serviços      (raro — out-of-scope MVP)
#
# Mapa padrão cobre o caso comum por anexo. Subdistinção locação×serviços
# dentro do Anexo III + tributação concentrada exigem override via
# parâmetro `subtipo_atividade` (out-of-scope desta sprint — quando
# primeiro cliente precisar, expandir `apuracao_fiscal.output_jsonb`
# com subtipo por linha de receita).
_ID_ATIVIDADE_POR_ANEXO: dict[str, int] = {
    "I": 1,
    "II": 2,
    "III": 4,
    "IV": 5,
    "V": 6,
}


# Subtipos override do Anexo III — quando passados pelo caller (futuro),
# substituem o ID padrão 4 pelo código específico do Manual SERPRO v1.4+.
_ID_ATIVIDADE_POR_SUBTIPO: dict[str, int] = {
    "locacao_bens_moveis": 3,
    "exportacao": 8,
    "tributacao_concentrada": 7,
}


def _id_atividade_por_anexo(anexo: str, subtipo: str | None = None) -> int:
    """Resolve ``idAtividade`` do PGDAS-D (Manual SERPRO v1.4+).

    Sprint 19.6 PR2 (#16). ``subtipo`` opcional permite distinguir
    casos específicos dentro do mesmo anexo (locação de bens móveis,
    exportação, tributação concentrada/ST). Sem subtipo, retorna o
    código do caso comum por anexo.
    """
    if subtipo is not None:
        codigo = _ID_ATIVIDADE_POR_SUBTIPO.get(subtipo)
        if codigo is not None:
            return codigo
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
