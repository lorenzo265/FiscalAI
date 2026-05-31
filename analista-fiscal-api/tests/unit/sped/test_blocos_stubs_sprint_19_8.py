"""Testes dos stubs de bloco SPED (Sprint 19.8 PR1 — #27, #29, #30, #32).

Verifica que os blocos stub (IND_MOV=1 + encerramento) aparecem no
arquivo gerado quando não há dados — defesa de leiaute (RFB exige
abertura+encerramento mesmo sem dados).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.sped.compartilhado import contar_registros
from app.modules.sped.efd.gerador_contribuicoes import (
    ApuracaoMensalPisCofins,
    EntradaEfdContribuicoes,
    IdentificacaoEmpresaEfd,
    gerar_efd_contribuicoes,
)
from app.modules.sped.efd.gerador_icms_ipi import (
    ApuracaoMensalIcms,
    EntradaEfdIcmsIpi,
    IdentificacaoEmpresaEfdIcms,
    gerar_efd_icms_ipi,
)


def _empresa_contrib() -> IdentificacaoEmpresaEfd:
    return IdentificacaoEmpresaEfd(
        cnpj="12345678000190",
        razao_social="Empresa Demo",
        nome_fantasia=None,
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
    )


def _empresa_icms() -> IdentificacaoEmpresaEfdIcms:
    return IdentificacaoEmpresaEfdIcms(
        cnpj="12345678000190",
        razao_social="Empresa Demo",
        nome_fantasia=None,
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
        inscricao_estadual="111222333",
    )


# ── #27 — EFD-Contribuições blocos I e P stub ──────────────────────────────


def test_efd_contribuicoes_emite_bloco_i_stub() -> None:
    """Bloco I (instituições financeiras) deve ter I001+I990 mesmo vazio."""
    entrada = EntradaEfdContribuicoes(
        empresa=_empresa_contrib(),
        competencia_inicio=date(2026, 5, 1),
        competencia_fim=date(2026, 5, 31),
        apuracao=ApuracaoMensalPisCofins(
            base_calculo_pis=Decimal("0"),
            aliquota_pis=Decimal("0.65"),
            valor_pis_apurado=Decimal("0"),
            valor_pis_a_recolher=Decimal("0"),
            base_calculo_cofins=Decimal("0"),
            aliquota_cofins=Decimal("3.00"),
            valor_cofins_apurado=Decimal("0"),
            valor_cofins_a_recolher=Decimal("0"),
        ),
    )
    arquivo = gerar_efd_contribuicoes(entrada)
    texto = arquivo.conteudo.decode("latin-1")
    regs = contar_registros(texto.splitlines())
    assert regs.get("I001") == 1
    assert regs.get("I990") == 1
    assert regs.get("P001") == 1
    assert regs.get("P990") == 1


def test_efd_contribuicoes_algoritmo_versao_v3() -> None:
    """Sprint 19.8 PR1 bump v2→v3."""
    from app.modules.sped.efd.gerador_contribuicoes import ALGORITMO_VERSAO

    assert ALGORITMO_VERSAO == "sped.efd_contribuicoes.v3"


# ── #30 — EFD ICMS-IPI Bloco B stub ────────────────────────────────────────


def test_efd_icms_ipi_emite_bloco_b_stub() -> None:
    """Bloco B (ISS RJ/SP) deve ter B001+B990 mesmo vazio."""
    entrada = EntradaEfdIcmsIpi(
        empresa=_empresa_icms(),
        competencia_inicio=date(2026, 5, 1),
        competencia_fim=date(2026, 5, 31),
        apuracao_icms=ApuracaoMensalIcms(
            valor_total_debitos=Decimal("0"),
            valor_total_creditos=Decimal("0"),
            saldo_credor_anterior=Decimal("0"),
            ajustes_devedores=Decimal("0"),
            ajustes_credores=Decimal("0"),
            valor_icms_a_recolher=Decimal("0"),
            saldo_credor_a_transportar=Decimal("0"),
        ),
    )
    arquivo = gerar_efd_icms_ipi(entrada)
    texto = arquivo.conteudo.decode("latin-1")
    regs = contar_registros(texto.splitlines())
    assert regs.get("B001") == 1
    assert regs.get("B990") == 1


def test_efd_icms_ipi_algoritmo_versao_v3() -> None:
    """Sprint 19.8 PR1 bump v2→v3."""
    from app.modules.sped.efd.gerador_icms_ipi import ALGORITMO_VERSAO

    assert ALGORITMO_VERSAO == "sped.efd_icms_ipi.v3"
