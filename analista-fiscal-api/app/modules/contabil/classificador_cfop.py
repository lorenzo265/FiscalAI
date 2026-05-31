"""Classificador determinístico de NF de entrada por CFOP.

Zero I/O. Determinístico. Golden-tested. Devolve a chave do mapa
``CODIGOS_PADRAO_LANCAMENTO_AUTO`` que aponta à conta de débito correta.

Escopo deliberado (§8.11 — out-of-scope declarado):
  * Apenas CFOPs de **entrada** das séries 1.xxx (interno) e 2.xxx
    (interestadual). NF de saída não usa este classificador — a conta de
    crédito é resolvida por ``nf.tipo`` (nfse → receita_servicos, nfe →
    receita_vendas) em ``lancador_auto.gerar_partidas_de_nfe``.
  * Sem dependência de NCM. Classificação por NCM (ex.: separar custo de
    medicamentos vs. eletrônicos) fica para a sprint AI advisor.
  * Fallback explícito ``outras_despesas`` (conta 5.1.99) garante que o
    pipeline nunca falha por CFOP desconhecido — a NF entra na contabilidade
    mesmo que classificada como "a reclassificar".

Mapa baseado nos CFOPs mais comuns para PME (Convênio S/N de 1970 + RICMS):
  * 1.101/2.101: Compra para industrialização → estoques
  * 1.102/2.102: Compra para comercialização → estoques
  * 1.556/2.556: Compra de bem para ativo imobilizado → imobilizado
  * 1.128/2.128: Compra de serviço usado em prestação → despesa_servicos
  * 1.933/2.933: Aquisição de serviço de comunicação → despesa_servicos
  * 1.949/2.949: Outras entradas → outras_despesas (fallback explícito)
"""

from __future__ import annotations

ALGORITMO_VERSAO = "cfop-classifier-2026.05"

# Fallback declarado — chave de ``CODIGOS_PADRAO_LANCAMENTO_AUTO``.
CONTA_FALLBACK_ENTRADA = "outras_despesas"

# Mapa CFOP → chave do CODIGOS_PADRAO_LANCAMENTO_AUTO.
_MAPA_CFOP_ENTRADA: dict[str, str] = {
    # Industrialização própria
    "1101": "estoques",
    "2101": "estoques",
    # Comercialização (revenda)
    "1102": "estoques",
    "2102": "estoques",
    # Bem para ativo imobilizado
    "1556": "imobilizado",
    "2556": "imobilizado",
    # Serviço usado em prestação
    "1128": "despesa_servicos",
    "2128": "despesa_servicos",
    # Serviço de comunicação
    "1933": "despesa_servicos",
    "2933": "despesa_servicos",
}


def classificar_conta_debito_entrada(cfop: str | None) -> str:
    """Retorna a chave de ``CODIGOS_PADRAO_LANCAMENTO_AUTO`` para o débito da NF.

    ``cfop`` aceita formato cru (``"1102"``) ou pontuado (``"1.102"``).
    Fallback para ``outras_despesas`` quando o CFOP é NULL, vazio, formato
    inválido, ou não está no mapa.
    """
    if not cfop:
        return CONTA_FALLBACK_ENTRADA
    digits = cfop.replace(".", "").strip()
    if len(digits) != 4 or not digits.isdigit():
        return CONTA_FALLBACK_ENTRADA
    return _MAPA_CFOP_ENTRADA.get(digits, CONTA_FALLBACK_ENTRADA)
