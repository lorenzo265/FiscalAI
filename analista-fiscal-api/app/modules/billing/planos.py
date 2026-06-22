"""Catálogo de planos de assinatura (Marco 2 — billing).

Constante pura, versionada em ``PLANOS_VERSAO`` (auditoria histórica de qual
snapshot de preços foi aplicado a cada assinatura). Planos MOCK iniciais —
preços que fazem sentido para PMEs (Simples/Lucro Presumido). Cada plano
referencia a CHAVE de env que guarda o Stripe Price ID (``stripe_price_env``);
em dev (sem Stripe), o ``_FakeBillingProvider`` ignora.

Bump ``PLANOS_VERSAO`` quando preço, limite ou estrutura mudarem.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

PLANOS_VERSAO: str = "billing-planos-2026.06"
TRIAL_DIAS: int = 14


@dataclass(frozen=True, slots=True)
class Plano:
    """Plano de assinatura mensal. ``preco_mensal`` em BRL (NUMERIC(14,2))."""

    codigo: str
    nome: str
    preco_mensal: Decimal
    descricao: str
    max_empresas: int
    stripe_price_env: str


_PLANOS: dict[str, Plano] = {
    "essencial": Plano(
        codigo="essencial",
        nome="Essencial",
        preco_mensal=Decimal("149.00"),
        descricao=(
            "MEI e Simples até R$ 360 mil/ano. 1 empresa. DAS/PGDAS, agenda "
            "fiscal, captura de NF-e, app + WhatsApp."
        ),
        max_empresas=1,
        stripe_price_env="STRIPE_PRICE_ESSENCIAL",
    ),
    "profissional": Plano(
        codigo="profissional",
        nome="Profissional",
        preco_mensal=Decimal("299.00"),
        descricao=(
            "Simples + Lucro Presumido até R$ 4,8 mi. Folha + eSocial, "
            "relatorios contabeis, assistente IA, conciliacao bancaria."
        ),
        max_empresas=1,
        stripe_price_env="STRIPE_PRICE_PROFISSIONAL",
    ),
    "avancado": Plano(
        codigo="avancado",
        nome="Avancado",
        preco_mensal=Decimal("499.00"),
        descricao=(
            "Multi-empresa (ate 5). SPED completo, EFD-Reinf, marketplace de "
            "contadores, suporte prioritario."
        ),
        max_empresas=5,
        stripe_price_env="STRIPE_PRICE_AVANCADO",
    ),
}


def plano_para(codigo: str) -> Plano:
    """Resolve o plano pelo codigo; levanta ``PlanoInexistente`` se nao houver."""
    from app.shared.exceptions import PlanoInexistente

    plano = _PLANOS.get(codigo)
    if plano is None:
        raise PlanoInexistente(f"Plano {codigo!r} nao existe no catalogo")
    return plano


def todos_os_planos() -> list[Plano]:
    """Catalogo completo, em ordem de preco crescente."""
    return list(_PLANOS.values())
