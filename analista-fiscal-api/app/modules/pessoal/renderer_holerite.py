"""Renderer de holerite — texto markdown sem deps externas.

Sprint 19.6 PR4 (#11). Substitui `storage_key=NULL` permanente por
renderização sob demanda + persistência opcional no storage.

**Decisão arquitetural:**

  * MVP: renderer **texto/markdown** — zero deps externas, pesa <2KB
    por holerite, abre em qualquer dispositivo. Suficiente pra envio
    via WhatsApp ou e-mail.
  * Renderer **PDF binário** fica opt-in (reportlab) para sprint
    dedicada quando primeiro cliente exigir PDF visual (alvará,
    licitação). PR mais simples: trocar `renderizar_texto` por
    `renderizar_pdf` no service consumidor.

Pure function — recebe Holerite + Funcionario, devolve `bytes` UTF-8
encoded. Sem I/O. Caller persiste no storage e popula `storage_key`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.shared.db.models import Funcionario, Holerite


def renderizar_holerite_texto(
    holerite: Holerite, funcionario: Funcionario, *, empresa_nome: str
) -> bytes:
    """Renderiza holerite em texto markdown UTF-8.

    Estrutura (compatível com WhatsApp + e-mail + visualização texto):

        Holerite — <empresa>
        <competência>

        Funcionário: <nome>
        CPF: <cpf>
        Cargo: <cargo>
        Vínculo: <vinculo>

        ─ Proventos ─
        Salário Bruto       R$ <bruto>

        ─ Descontos ─
        INSS    <alíquota>%  R$ <inss>
        IRRF                R$ <irrf>

        ─ Resumo ─
        Total Bruto         R$ <bruto>
        Total Descontos     R$ <descontos>
        Líquido a Receber   R$ <liquido>

        FGTS (empregador)   R$ <fgts>
        Algoritmo: <algoritmo_versao>

    Princípio §8.5: cada valor é a fonte de verdade do banco (sem
    cálculo inline). Auditável palavra-por-palavra.
    """
    linhas: list[str] = []
    linhas.append(f"Holerite — {empresa_nome}")
    linhas.append(_competencia_br(holerite.competencia))
    linhas.append("")
    linhas.append(f"Funcionário: {funcionario.nome}")
    linhas.append(f"CPF: {_formatar_cpf(funcionario.cpf)}")
    if funcionario.cargo:
        linhas.append(f"Cargo: {funcionario.cargo}")
    linhas.append(f"Vínculo: {funcionario.vinculo}")
    linhas.append("")
    linhas.append("─ Proventos ─")
    linhas.append(_linha_valor("Salário Bruto", holerite.salario_bruto))
    linhas.append("")
    linhas.append("─ Descontos ─")
    aliq_pct = (
        holerite.inss_aliquota_efetiva * Decimal("100")
    ).quantize(Decimal("0.01"))
    linhas.append(
        f"INSS  {aliq_pct}%  {_real(holerite.inss_empregado)}"
    )
    if holerite.irrf > Decimal("0"):
        linhas.append(_linha_valor("IRRF", holerite.irrf))
    linhas.append("")
    total_descontos = holerite.inss_empregado + holerite.irrf
    linhas.append("─ Resumo ─")
    linhas.append(_linha_valor("Total Bruto", holerite.salario_bruto))
    linhas.append(_linha_valor("Total Descontos", total_descontos))
    linhas.append(_linha_valor("Líquido a Receber", holerite.valor_liquido))
    linhas.append("")
    linhas.append(_linha_valor("FGTS (empregador)", holerite.fgts_empregador))
    linhas.append(f"Algoritmo: {holerite.algoritmo_versao}")

    return ("\n".join(linhas) + "\n").encode("utf-8")


def chave_storage_holerite(holerite: Holerite) -> str:
    """Sprint 19.6 PR4 (#11) — chave determinística no storage.

    Pattern: ``tenant/<id>/empresa/<id>/holerite/<comp>/<holerite_id>.md``.
    Prefixo `tenant/empresa` permite IAM no S3 por tenant (LGPD §8.7).
    """
    return (
        f"tenant/{holerite.tenant_id}/empresa/"
        f"{holerite.folha_mensal_id}/holerite/"
        f"{holerite.competencia.isoformat()}/"
        f"{holerite.id}.md"
    )


def _linha_valor(rotulo: str, valor: Decimal) -> str:
    return f"{rotulo}: {_real(valor)}"


def _real(valor: Decimal) -> str:
    """Formata R$ com 2 decimais — sem locale (compat WhatsApp ASCII)."""
    return f"R$ {valor.quantize(Decimal('0.01'))}"


def _competencia_br(d: date) -> str:
    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    return f"{meses[d.month - 1]}/{d.year}"


def _formatar_cpf(cpf: str) -> str:
    """111.222.333-44 — só estética para o texto."""
    if len(cpf) != 11 or not cpf.isdigit():
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


__all__ = [
    "chave_storage_holerite",
    "renderizar_holerite_texto",
]
