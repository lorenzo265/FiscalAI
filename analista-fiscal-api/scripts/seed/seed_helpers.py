"""Funções puras para o seed sintético (Sprint 19 PR3).

Zero I/O — todas as funções aqui são determinísticas e testáveis isoladamente.
Cobertas por ``tests/perf/test_seed_helpers.py``.

Determinismo: tudo deriva de ``(tipo, idx_seed)``. Re-execução produz o
mesmo dataset — útil para reproduzir bugs de perf e para idempotência
do orquestrador via ``ON CONFLICT``.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

# Namespace estável para todos os UUIDs sintéticos. Mudar isto é breaking
# change (invalida datasets seedados anteriormente).
SEED_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-fa1ca1100000")


def seed_uuid(tipo: str, *partes: object) -> uuid.UUID:
    """UUID5 determinístico no namespace do seed.

    Exemplo: ``seed_uuid("tenant", 42)`` → mesmo UUID sempre.
    Combine partes hierarquicamente: ``seed_uuid("empresa", tenant_idx, emp_idx)``.
    """
    chave = "|".join(str(p) for p in (tipo, *partes))
    return uuid.uuid5(SEED_NAMESPACE, chave)


# ─────────────────────────────────────────────────────────────────────────────
# CNPJ
# ─────────────────────────────────────────────────────────────────────────────


def calcular_dv_cnpj(base_12: str) -> str:
    """Calcula os 2 dígitos verificadores do CNPJ a partir dos 12 primeiros.

    Algoritmo oficial RFB: dois pesos crescentes a partir de 2 (resetando em
    9), módulo 11. Se resto < 2, DV = 0; senão DV = 11 - resto.
    """
    if len(base_12) != 12 or not base_12.isdigit():
        raise ValueError("base do CNPJ deve ter exatamente 12 dígitos")

    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_1 = sum(int(base_12[i]) * pesos_1[i] for i in range(12))
    resto_1 = soma_1 % 11
    d1 = 0 if resto_1 < 2 else 11 - resto_1

    base_13 = base_12 + str(d1)
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_2 = sum(int(base_13[i]) * pesos_2[i] for i in range(13))
    resto_2 = soma_2 % 11
    d2 = 0 if resto_2 < 2 else 11 - resto_2

    return f"{d1}{d2}"


def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ (14 dígitos, DV correto). Não aceita sequências repetidas."""
    digitos = "".join(c for c in cnpj if c.isdigit())
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    return calcular_dv_cnpj(digitos[:12]) == digitos[12:]


def gerar_cnpj_seed(tenant_idx: int, empresa_idx: int) -> str:
    """Gera CNPJ válido determinístico para o seed.

    Base: ``42`` + 6 dígitos do tenant_idx + ``0001`` (matriz). Calcula DV.

    Garantia: cada (tenant_idx, empresa_idx) produz CNPJ único e válido.
    O ``42`` no início torna fácil identificar visualmente CNPJs sintéticos
    em logs (CNPJs reais começam com qualquer dígito, mas a coincidência
    é improvável em um dataset de teste).
    """
    # 14 = 2 (prefixo) + 8 (índice composto) + 4 (filial)
    indice = (tenant_idx * 17 + empresa_idx) % 100_000_000
    base = f"42{indice:08d}{empresa_idx % 10:01d}001"[:12]
    return base + calcular_dv_cnpj(base)


# ─────────────────────────────────────────────────────────────────────────────
# Datas
# ─────────────────────────────────────────────────────────────────────────────


def competencias_dos_ultimos_meses(referencia: date, n: int) -> list[date]:
    """Retorna ``n`` competências (primeiro dia do mês) terminando em ``referencia``.

    Sempre normaliza para dia 1. ``n=12`` partindo de 2026-05-15 →
    ``[2025-06-01, 2025-07-01, ..., 2026-05-01]``.
    """
    if n <= 0:
        return []
    ano = referencia.year
    mes = referencia.month
    resultado: list[date] = []
    for _ in range(n):
        resultado.append(date(ano, mes, 1))
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1
    return list(reversed(resultado))


# ─────────────────────────────────────────────────────────────────────────────
# Valores sintéticos
# ─────────────────────────────────────────────────────────────────────────────


def receita_mensal_sintetica(tenant_idx: int, empresa_idx: int, mes: int) -> Decimal:
    """Receita mensal pseudoaleatória mas determinística.

    Range típico R$ 15k – R$ 90k para Simples Nacional / Lucro Presumido
    pequeno. Sazonalidade simples: variação ±20% pelo mês.
    """
    base = Decimal("30000") + Decimal((tenant_idx * 7919 + empresa_idx * 31) % 60000)
    sazonalidade = Decimal("1") + Decimal((mes % 4) - 2) / Decimal("10")
    valor = (base * sazonalidade).quantize(Decimal("0.01"))
    if valor < Decimal("100"):
        valor = Decimal("100")
    return valor


def rbt12_sintetico(tenant_idx: int, empresa_idx: int) -> Decimal:
    """RBT12 que sempre cai na faixa 3 do Anexo I (alíquota 9,50%).

    R$ 600k – R$ 700k mantém a empresa estável no Simples Nacional sem bater
    em sublimites estaduais nem no teto federal de R$ 4,8M — útil para load
    test não disparar exceções de regime.
    """
    base = Decimal("600000")
    delta = Decimal((tenant_idx * 1013 + empresa_idx * 41) % 100_000)
    return (base + delta).quantize(Decimal("0.01"))


# ─────────────────────────────────────────────────────────────────────────────
# Slugs / nomes
# ─────────────────────────────────────────────────────────────────────────────


def tenant_slug(idx: int) -> str:
    """Slug determinístico do tenant. Padrão ``loadtest-XXXX`` (zero-padded)."""
    return f"loadtest-{idx:04d}"


def empresa_razao_social(tenant_idx: int, empresa_idx: int) -> str:
    return f"Empresa Sintética {tenant_idx:04d}-{empresa_idx:02d} LTDA"


def usuario_email_seed(tenant_idx: int) -> str:
    """Email determinístico do usuário admin de cada tenant sintético."""
    return f"admin+{tenant_idx:04d}@loadtest.fiscalai.invalid"
