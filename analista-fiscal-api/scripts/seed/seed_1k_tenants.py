"""Seed sintético de tenants/usuários/empresas (Sprint 19 PR3).

Uso (PowerShell):

  poetry run python -m scripts.seed.seed_1k_tenants --scale smoke
  poetry run python -m scripts.seed.seed_1k_tenants --scale moderate
  poetry run python -m scripts.seed.seed_1k_tenants --scale full

Saídas:
  * Linhas em ``tenant``, ``usuario``, ``empresa`` (idempotente via uuid5
    + ON CONFLICT DO NOTHING — re-execução é segura).
  * Arquivo ``tests/load/.seed/empresas.json`` com lista de
    ``{empresa_id, tenant_id, jwt, regime, cnpj}`` que o k6 lê para
    hitar os endpoints com autenticação válida.

Princípios cravados:
  * §8.9 idempotência — re-rodar não duplica nem quebra constraints.
  * §8.1 RLS — script roda como superuser fiscal (bypass policies);
    nunca chamar este pipeline em prod.
  * §8.7 LGPD — todos os dados gerados aqui são sintéticos
    (CNPJ válido mas começa com 42; emails em ``@loadtest.fiscalai.invalid``).

**Não é para produção.** Falha-rápido se ``settings.ENVIRONMENT == 'prod'``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Environment, get_settings
from app.shared.auth.jwt import TenantContext, criar_token
from app.shared.db.models import Empresa, Tenant, Usuario
from app.shared.db.perf import build_async_engine
from scripts.seed.cardinality import PRESETS, SeedCardinality, resolver_preset
from scripts.seed.seed_helpers import (
    empresa_razao_social,
    gerar_cnpj_seed,
    rbt12_sintetico,
    seed_uuid,
    tenant_slug,
    usuario_email_seed,
)

log = structlog.get_logger(__name__)

# Hash bcrypt inutilizável — login via senha não funciona, k6 usa JWT direto.
_SENHA_HASH_PLACEHOLDER = (
    "$2b$04$LOADTESTPLACEHOLDERHASHNOLOGINPOSSIBLEBYDESIGN12345xx"
)

# UF arbitrária mas válida; SP cai em sublimite de R$ 3,6M (default) — OK.
_UF_PADRAO = "SP"
_MUNICIPIO_IBGE_SP = "3550308"  # São Paulo capital


def _empresa_id(tenant_idx: int, empresa_idx: int) -> UUID:
    return seed_uuid("empresa", tenant_idx, empresa_idx)


def _build_tenant_rows(card: SeedCardinality) -> list[dict[str, object]]:
    return [
        {
            "id": seed_uuid("tenant", idx),
            "nome": f"Tenant Load Test #{idx:04d}",
            "slug": tenant_slug(idx),
            "ativo": True,
        }
        for idx in range(card.tenants)
    ]


def _build_usuario_rows(card: SeedCardinality) -> list[dict[str, object]]:
    return [
        {
            "id": seed_uuid("usuario", idx),
            "tenant_id": seed_uuid("tenant", idx),
            "email": usuario_email_seed(idx),
            "senha_hash": _SENHA_HASH_PLACEHOLDER,
            "nome": f"Admin {idx:04d}",
            "ativo": True,
        }
        for idx in range(card.tenants)
    ]


def _build_empresa_rows(card: SeedCardinality) -> list[dict[str, object]]:
    linhas: list[dict[str, object]] = []
    for t_idx in range(card.tenants):
        for e_idx in range(card.empresas_por_tenant):
            linhas.append(
                {
                    "id": _empresa_id(t_idx, e_idx),
                    "tenant_id": seed_uuid("tenant", t_idx),
                    "cnpj": gerar_cnpj_seed(t_idx, e_idx),
                    "razao_social": empresa_razao_social(t_idx, e_idx),
                    "nome_fantasia": None,
                    "regime_tributario": "simples_nacional",
                    "perfil_ui": "sn_sem_funcionarios",
                    "anexo_simples": "I",
                    "cnae_principal": "4781400",  # comércio varejista de vestuário
                    "municipio": "São Paulo",
                    "codigo_municipio_ibge": _MUNICIPIO_IBGE_SP,
                    "uf": _UF_PADRAO,
                    "faturamento_12m": rbt12_sintetico(t_idx, e_idx),
                    "ativa": True,
                }
            )
    return linhas


async def _bulk_insert_idempotente(
    session: AsyncSession,
    modelo: type,
    valores: list[dict[str, object]],
    index_elements: Iterable[str] = ("id",),
) -> int:
    """Bulk INSERT ... ON CONFLICT DO NOTHING. Retorna nº de linhas afetadas."""
    if not valores:
        return 0
    stmt = pg_insert(modelo).values(valores).on_conflict_do_nothing(
        index_elements=list(index_elements)
    )
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def _seed(card: SeedCardinality, output_path: Path) -> dict[str, int]:
    """Pipeline principal — retorna contadores para logging."""
    settings = get_settings()
    if settings.ENVIRONMENT is Environment.PROD:
        raise RuntimeError("Seed sintético JAMAIS roda em ENVIRONMENT=prod")

    engine = build_async_engine(settings)
    sess_factory = async_sessionmaker(engine, expire_on_commit=False)

    log.info(
        "seed.iniciado",
        preset=card.nome,
        tenants=card.tenants,
        empresas_total=card.total_empresas,
        database=settings.DATABASE_URL.split("@")[-1],
    )

    try:
        async with sess_factory() as session:
            tenants_novos = await _bulk_insert_idempotente(
                session, Tenant, _build_tenant_rows(card)
            )
            usuarios_novos = await _bulk_insert_idempotente(
                session, Usuario, _build_usuario_rows(card)
            )
            empresas_novas = await _bulk_insert_idempotente(
                session, Empresa, _build_empresa_rows(card)
            )
            await session.commit()
    finally:
        await engine.dispose()

    # Emite tokens.json fora da transação — derivação determinística.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    empresas_fixtures = _build_fixtures(card)
    fixtures_doc: dict[str, object] = {
        "preset": card.nome,
        "empresas": empresas_fixtures,
    }
    output_path.write_text(json.dumps(fixtures_doc, indent=2), encoding="utf-8")
    total_fixtures = len(empresas_fixtures)

    log.info(
        "seed.concluido",
        preset=card.nome,
        tenants_inseridos=tenants_novos,
        usuarios_inseridos=usuarios_novos,
        empresas_inseridas=empresas_novas,
        fixtures_emitidas=total_fixtures,
        output=str(output_path),
    )
    return {
        "tenants_inseridos": tenants_novos,
        "usuarios_inseridos": usuarios_novos,
        "empresas_inseridas": empresas_novas,
        "fixtures_emitidas": total_fixtures,
    }


def _build_fixtures(card: SeedCardinality) -> list[dict[str, str]]:
    """Constrói a lista de empresas+jwt consumida pelo k6.

    Cada item:
      {"empresa_id": "...", "tenant_id": "...", "jwt": "...",
       "regime": "simples_nacional", "cnpj": "..."}
    """
    empresas: list[dict[str, str]] = []
    for t_idx in range(card.tenants):
        tenant_id = seed_uuid("tenant", t_idx)
        usuario_id = seed_uuid("usuario", t_idx)
        token, _ttl = criar_token(
            TenantContext(tenant_id=tenant_id, usuario_id=usuario_id)
        )
        for e_idx in range(card.empresas_por_tenant):
            empresas.append(
                {
                    "empresa_id": str(_empresa_id(t_idx, e_idx)),
                    "tenant_id": str(tenant_id),
                    "jwt": token,
                    "regime": "simples_nacional",
                    "cnpj": gerar_cnpj_seed(t_idx, e_idx),
                }
            )
    return empresas


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed sintético para load testing (Sprint 19 PR3)",
    )
    parser.add_argument(
        "--scale",
        choices=sorted(PRESETS),
        default="smoke",
        help="Preset de escala (default: smoke)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/load/.seed/empresas.json"),
        help="Caminho do JSON de fixtures que o k6 vai consumir",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    card = resolver_preset(args.scale)
    contadores = asyncio.run(_seed(card, args.output))
    print(
        f"\nSeed '{card.nome}' concluído: "
        f"{contadores['tenants_inseridos']} tenants, "
        f"{contadores['usuarios_inseridos']} usuários, "
        f"{contadores['empresas_inseridas']} empresas inseridas "
        f"(idempotente — totais 0 indicam re-execução). "
        f"Fixtures: {args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
