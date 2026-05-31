"""Snapshot determinístico do contexto da empresa (Sprint 13 PR2).

Captura os atributos relevantes da PME no momento da abertura da consulta —
versão preservada em ``snapshot_versao`` para evolução compatível. Conteúdo
mínimo necessário para o contador parceiro contextualizar a pergunta sem
acessar o resto do tenant.

Sem PII granular além de razão social + CNPJ — escolha consciente (§8.7):
detalhamento adicional (sócios, folha) só com consentimento explícito por
campo, fica para sprint futura.
"""

from __future__ import annotations

from app.shared.db.models import Empresa
from app.shared.types import JsonObject

SNAPSHOT_VERSAO: str = "v1"


def snapshot_empresa(empresa: Empresa) -> JsonObject:
    """Devolve dicionário JSONB-serializable com o contexto v1.

    Decimal e UUID viram string explicitamente para serialização
    determinística (mesmo input → mesmo bytes, base do ``pergunta_hash``).
    """
    return {
        "razao_social": empresa.razao_social,
        "nome_fantasia": empresa.nome_fantasia,
        "cnpj": empresa.cnpj,
        "regime_tributario": empresa.regime_tributario,
        "perfil_ui": empresa.perfil_ui,
        "anexo_simples": empresa.anexo_simples,
        "cnae_principal": empresa.cnae_principal,
        "municipio": empresa.municipio,
        "uf": empresa.uf,
        "faturamento_12m": (
            str(empresa.faturamento_12m) if empresa.faturamento_12m is not None else None
        ),
    }
