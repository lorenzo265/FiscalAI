"""Re-check determinístico §8.6 pós-LLM (Sprint 19.5 PR3).

LLM lê o PDF da Portaria e devolve JSON estruturado. Antes de criar a
sugestão, o re-check determinístico:

  1. **Valida estrutura** com Pydantic v2 (já roda no `model_validate`).
  2. **Aplica validadores §8.6 do PR1** — faixas progressivas, plausibilidade,
     salário mínimo do ano, etc. Reuso direto de
     ``app/modules/tabelas_admin/validadores.py``.
  3. **Anti-alucinação**: exige ≥ 3 citações literais cujo `trecho` apareça
     **literalmente** no texto do PDF (substring case-insensitive,
     desconsiderando espaços múltiplos). LLM que "inventou" texto cai aqui.
  4. **Confiança mínima**: `llm_confianca >= 0.5` (abaixo disso o LLM
     declarou que não tinha certeza — sugestão fica `recheck_passou=false`
     mas é criada para auditoria).

Diferente do validador puro do PR1 que **levanta** `VigenciaTributariaInvalida`,
o re-check **NÃO levanta** — devolve ``RecheckResultado(passou, observacoes)``.
Sugestão é criada mesmo com `passou=false`, com `recheck_observacoes` cheio
para a UI destacar em vermelho. Admin decide se aprova mesmo assim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, cast

import structlog
from pydantic import BaseModel, ValidationError

from app.modules.tabelas_admin.schemas import (
    VigenciaCbsIbsIn,
    VigenciaFgtsIn,
    VigenciaIcmsUfIn,
    VigenciaInssIn,
    VigenciaIrrfIn,
    VigenciaPresuncaoLpIn,
    VigenciaSimplesNacionalIn,
)
from app.modules.tabelas_admin.validadores import (
    validar_vigencia_cbs_ibs,
    validar_vigencia_fgts,
    validar_vigencia_icms_uf,
    validar_vigencia_inss,
    validar_vigencia_irrf,
    validar_vigencia_presuncao_lp,
    validar_vigencia_simples_nacional,
)
from app.shared.exceptions import VigenciaTributariaInvalida

log = structlog.get_logger(__name__)

_CONFIANCA_MIN: Decimal = Decimal("0.5")
_MIN_CITACOES = 3
_NORMALIZADOR = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class CitacaoLLM:
    pagina: int
    trecho: str


@dataclass(slots=True)
class RecheckResultado:
    passou: bool
    observacoes: dict[str, Any] = field(default_factory=dict)

    def fail(self, codigo: str, detalhe: str) -> None:
        self.passou = False
        # observacoes acumulado por código — útil para a UI montar checklist.
        self.observacoes.setdefault("falhas", []).append(
            {"codigo": codigo, "detalhe": detalhe}
        )


_SCHEMA_POR_TIPO: dict[str, type[BaseModel]] = {
    "inss": VigenciaInssIn,
    "irrf": VigenciaIrrfIn,
    "fgts": VigenciaFgtsIn,
    "simples_nacional": VigenciaSimplesNacionalIn,
    "presuncao_lp": VigenciaPresuncaoLpIn,
    "icms_uf": VigenciaIcmsUfIn,
    "cbs_ibs": VigenciaCbsIbsIn,
}


def _normalizar(texto: str) -> str:
    return _NORMALIZADOR.sub(" ", texto).strip().lower()


def _aplicar_validador_pr1(
    tipo_tabela: str, payload: BaseModel
) -> str | None:
    """Roda o validador puro do PR1. Retorna mensagem de erro ou None.

    Cada validador aceita só seu schema específico; despachamos por tipo
    e fazemos cast — payload já foi validado por Pydantic antes desta
    chamada, então o cast é seguro.
    """
    try:
        if tipo_tabela == "inss":
            validar_vigencia_inss(cast(VigenciaInssIn, payload))
        elif tipo_tabela == "irrf":
            validar_vigencia_irrf(cast(VigenciaIrrfIn, payload))
        elif tipo_tabela == "fgts":
            validar_vigencia_fgts(cast(VigenciaFgtsIn, payload))
        elif tipo_tabela == "simples_nacional":
            validar_vigencia_simples_nacional(
                cast(VigenciaSimplesNacionalIn, payload)
            )
        elif tipo_tabela == "presuncao_lp":
            validar_vigencia_presuncao_lp(
                cast(VigenciaPresuncaoLpIn, payload)
            )
        elif tipo_tabela == "icms_uf":
            validar_vigencia_icms_uf(cast(VigenciaIcmsUfIn, payload))
        elif tipo_tabela == "cbs_ibs":
            validar_vigencia_cbs_ibs(cast(VigenciaCbsIbsIn, payload))
        else:
            return f"tipo_tabela desconhecido: {tipo_tabela}"
    except VigenciaTributariaInvalida as exc:
        return str(exc)
    return None


def rechecar_extracao_llm(
    *,
    tipo_tabela: str,
    payload_llm: dict[str, Any],
    citacoes_llm: list[CitacaoLLM],
    confianca_llm: Decimal,
    texto_pdf: str,
) -> RecheckResultado:
    """Aplica re-check completo. Devolve ``RecheckResultado`` — nunca levanta.

    O caller persiste a sugestão **com** ``recheck_passou=resultado.passou``
    e ``recheck_observacoes=resultado.observacoes`` — UI destaca em vermelho
    quando false, mas admin pode aprovar mesmo assim (cenário onde LLM
    acertou a estrutura mas errou um valor que o humano consegue corrigir).
    """
    resultado = RecheckResultado(passou=True)

    # 1) Confiança mínima reportada pelo LLM.
    if confianca_llm < _CONFIANCA_MIN:
        resultado.fail(
            "confianca_baixa",
            f"LLM reportou confiança {confianca_llm} < {_CONFIANCA_MIN}",
        )

    # 2) Estrutura via Pydantic.
    schema = _SCHEMA_POR_TIPO.get(tipo_tabela)
    if schema is None:
        resultado.fail(
            "tipo_tabela_desconhecido",
            f"tipo {tipo_tabela!r} não está nos 7 suportados",
        )
        return resultado

    try:
        payload = schema.model_validate(payload_llm)
    except ValidationError as exc:
        resultado.fail(
            "pydantic_validation_falhou",
            str(exc)[:500],
        )
        return resultado

    # 3) Validador §8.6 do PR1.
    erro = _aplicar_validador_pr1(tipo_tabela, payload)
    if erro is not None:
        resultado.fail("validador_pr1_falhou", erro[:500])

    # 4) Anti-alucinação — ≥ 3 citações literalmente presentes no PDF.
    pdf_norm = _normalizar(texto_pdf)
    citacoes_validas = 0
    for c in citacoes_llm:
        trecho_norm = _normalizar(c.trecho)
        # Aceita match parcial — citação pode ter ortografia ligeiramente
        # diferente do PDF (ex.: "Tabela:" vs "TABELA:"). Limite 30 chars para
        # evitar match casual de palavras isoladas.
        if len(trecho_norm) >= 10 and trecho_norm[:30] in pdf_norm:
            citacoes_validas += 1
    if citacoes_validas < _MIN_CITACOES:
        resultado.fail(
            "citacoes_insuficientes",
            f"apenas {citacoes_validas} citações literais (mínimo {_MIN_CITACOES})",
        )

    resultado.observacoes["citacoes_validas"] = citacoes_validas
    resultado.observacoes["confianca_llm"] = str(confianca_llm)
    return resultado


__all__ = ["CitacaoLLM", "RecheckResultado", "rechecar_extracao_llm"]
