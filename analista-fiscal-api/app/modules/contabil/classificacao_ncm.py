"""Classificação de NF de entrada por NCM (Sprint 19.7 PR4 #5).

Refinamento do `classificador_cfop`: quando o CFOP cai em fallback
``outras_despesas`` (ex.: 1.949/2.949 — "outras entradas") **e** a NF
tem NCM informado, este módulo sugere uma conta mais específica via
heurística determinística por capítulo NCM (2 primeiros dígitos da
classificação NCM = 99 capítulos do SH).

**Princípios cravados:**

  * §8.5 — Toda sugestão carrega uma "citação" textual (capítulo NCM
    + descrição RFB). Sem citação válida, a função retorna ``None`` —
    nunca emite sugestão sem rastro auditável.
  * §8.6 — Re-check determinístico: a conta sugerida deve existir em
    ``CODIGOS_PADRAO_LANCAMENTO_AUTO``; caso contrário, suprime sugestão.
  * §8.8 — **Esta função é leitura, não fato.** `lancador_auto` continua
    emitindo o lançamento em ``outras_despesas`` (5.1.99) determinísticamente.
    Admin vê a sugestão num painel separado e decide re-lançar (sprint
    futura — re-lançamento via `LancadorService.relancar`). LLM nunca
    escreve fato direto.

Hoje a função é puramente heurística (determinística). A integração com
LLM Camada 3 (Gemini Flash + `recheck_llm` da Sprint 19.5) entra quando
o primeiro cliente com NCMs ambíguos aparecer no piloto — esta camada
preserva a interface (mesma assinatura), troca apenas a implementação
de ``sugerir_conta_por_ncm``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.modules.contabil.plano_referencial import (
    CODIGOS_PADRAO_LANCAMENTO_AUTO,
)

ALGORITMO_VERSAO: Final = "classificacao_ncm.v1"


@dataclass(frozen=True, slots=True)
class SugestaoClassificacao:
    """Saída da heurística NCM — input pra painel de revisão admin.

    Não é persistida automaticamente — admin que cria registro em
    `sugestao_classificacao_conta` (tabela vem em sprint dedicada quando
    LLM real entrar). Para já, service usa diretamente em log estruturado.
    """

    chave_conta_sugerida: str  # chave de ``CODIGOS_PADRAO_LANCAMENTO_AUTO``
    capitulo_ncm: str  # 2 dígitos
    descricao_capitulo: str  # citação RFB (§8.5)
    confianca: str  # 'alta' | 'media' | 'baixa'
    algoritmo_versao: str = ALGORITMO_VERSAO


# Mapa capítulo NCM (2 primeiros dígitos) → (chave_conta, descrição RFB,
# confiança). Cobre os capítulos mais comuns em PMEs brasileiras. Itens
# fora desse mapa não geram sugestão (cai em ``outras_despesas`` no
# lançamento real e admin reclassifica manualmente).
#
# Confiança:
#   * 'alta'  — NCM aponta claramente pra tipo de bem/serviço único.
#   * 'media' — NCM pode ser estoque ou imobilizado dependendo do uso.
#   * 'baixa' — heurística genérica (admin deve revisar).
_MAPA_CAPITULO_NCM: Final[dict[str, tuple[str, str, str]]] = {
    # Comestíveis + bebidas (capítulos 02-24) → estoque (revenda PME).
    "02": ("estoques", "Carnes e miudezas comestíveis", "alta"),
    "03": ("estoques", "Peixes e crustáceos", "alta"),
    "04": ("estoques", "Laticínios, ovos e mel", "alta"),
    "07": ("estoques", "Produtos hortícolas", "alta"),
    "08": ("estoques", "Frutas, cascas de cítricos", "alta"),
    "09": ("estoques", "Café, chá, mate e especiarias", "alta"),
    "10": ("estoques", "Cereais", "alta"),
    "11": ("estoques", "Farinhas e amidos", "alta"),
    "15": ("estoques", "Gorduras e óleos", "alta"),
    "16": ("estoques", "Preparações de carne, peixe", "alta"),
    "17": ("estoques", "Açúcares e produtos de confeitaria", "alta"),
    "18": ("estoques", "Cacau e suas preparações", "alta"),
    "19": ("estoques", "Preparações à base de cereais", "alta"),
    "20": ("estoques", "Preparações de produtos hortícolas", "alta"),
    "21": ("estoques", "Preparações alimentícias diversas", "alta"),
    "22": ("estoques", "Bebidas, líquidos alcoólicos e vinagres", "alta"),
    # Têxteis (capítulos 50-63) → estoque (varejo de moda).
    "50": ("estoques", "Seda", "alta"),
    "52": ("estoques", "Algodão", "alta"),
    "61": ("estoques", "Vestuário de malha", "alta"),
    "62": ("estoques", "Vestuário não-malha", "alta"),
    "63": ("estoques", "Têxteis confeccionados", "alta"),
    "64": ("estoques", "Calçados, polainas", "alta"),
    "65": ("estoques", "Chapéus e artefatos para cabeça", "alta"),
    # Máquinas/eletrônicos (84-85) → maior parte é estoque revenda, mas
    # bens >R$1.200 individuais podem ser imobilizado (CPC 27). Confiança
    # 'media' — admin tem que olhar.
    "84": ("estoques", "Máquinas e aparelhos mecânicos", "media"),
    "85": ("estoques", "Máquinas e aparelhos elétricos", "media"),
    # Veículos (87) — quase sempre imobilizado em PME.
    "87": ("imobilizado", "Veículos automotores", "alta"),
    # Instrumentos de precisão (90) — pode ser estoque ou imobilizado.
    "90": ("imobilizado", "Instrumentos ópticos, médicos", "media"),
    # Móveis (94) — geralmente imobilizado (mobiliário escritório).
    "94": ("imobilizado", "Móveis, mobiliário médico-cirúrgico", "alta"),
    # Brinquedos (95) → estoque (revenda).
    "95": ("estoques", "Brinquedos, jogos, artigos esportivos", "alta"),
}


def sugerir_conta_por_ncm(
    ncm: str | None,
    *,
    cfop: str | None = None,
) -> SugestaoClassificacao | None:
    """Heurística determinística NCM → chave de conta.

    Retorna ``None`` quando:
      * NCM ausente, vazio ou inválido (< 2 dígitos numéricos).
      * Capítulo NCM (2 primeiros dígitos) fora do mapa coberto.
      * Conta sugerida não existe em ``CODIGOS_PADRAO_LANCAMENTO_AUTO``
        (defesa em profundidade — §8.6 re-check).

    Args:
        ncm: classificação NCM completa (4 ou 8 dígitos). Aceita formato
            pontuado ``"8525.81.10"`` ou cru ``"85258110"``.
        cfop: CFOP da NF (opcional). Quando o CFOP **não** aponta pra
            fallback ``outras_despesas``, a função retorna ``None``
            (CFOP já classifica suficiente — não polui o painel admin).

    Returns:
        ``SugestaoClassificacao`` com chave de ``CODIGOS_PADRAO_LANCAMENTO_AUTO``
        + citação textual auditável.
    """
    if cfop is not None:
        from app.modules.contabil.classificador_cfop import (
            CONTA_FALLBACK_ENTRADA,
            classificar_conta_debito_entrada,
        )

        chave_cfop = classificar_conta_debito_entrada(cfop)
        if chave_cfop != CONTA_FALLBACK_ENTRADA:
            return None

    if not ncm:
        return None
    digitos = ncm.replace(".", "").replace("-", "").strip()
    if len(digitos) < 2 or not digitos.isdigit():
        return None

    capitulo = digitos[:2]
    par = _MAPA_CAPITULO_NCM.get(capitulo)
    if par is None:
        return None
    chave, descricao, confianca = par

    if chave not in CODIGOS_PADRAO_LANCAMENTO_AUTO:
        return None

    return SugestaoClassificacao(
        chave_conta_sugerida=chave,
        capitulo_ncm=capitulo,
        descricao_capitulo=descricao,
        confianca=confianca,
    )
