from __future__ import annotations

import re

from app.shared.llm.client import FonteFato, LLMResponse

# Resposta padrão quando a citação falha ou LLM alucina — nunca propagar resposta inválida
RESPOSTA_PADRAO_VERIFICAR = (
    "Vou verificar essa informação com mais cuidado. "
    "Por favor, consulte seu contador para confirmar."
)

# Padrões que indicam perguntas fora do escopo do produto
# Cada categoria mapeia para um tipo de encaminhamento no marketplace de contadores
OUT_OF_SCOPE_PATTERNS: dict[str, list[str]] = {
    "contencioso_fiscal": [
        "auto de infração",
        "recurso administrativo",
        "defesa fiscal",
        "carf",
        "drj",
        "fiscalização",
        "mandado de segurança",
        "impugnação",
        "autuação",
        "delegacia da receita",
        "drf ",
        "infração fiscal",
        "processo administrativo fiscal",
    ],
    "societario": [
        "holding",
        "sucessão",
        "sócio entrando",
        "sócio saindo",
        "alteração contratual",
        "cisão",
        "fusão",
        "incorporação",
        "incorporar",
        "dissolução",
        "distrato",
        "transferência de quotas",
        "transferir",
        "aumento de capital",
    ],
    "planejamento_tributario": [
        "reduzir imposto",
        "planejamento tributário",
        "aproveitar incentivo",
        "incentivo fiscal",
        "incentivo estadual",
        "regime especial",
        "elisão fiscal",
        "otimização tributária",
        "benefício fiscal",
        "recof",
    ],
    "operacoes_complexas": [
        "importação",
        "exportação",
        "exporta para o exterior",
        "zona franca",
        "icms-st",
        "substituição tributária",
        "entreposto",
        "trânsito aduaneiro",
        "despacho aduaneiro",
        "siscoserv",
        "drawback",
    ],
}

# Regex para valores monetários em Real (R$)
_RE_VALOR = re.compile(
    r"R\$\s*[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?",
    re.IGNORECASE,
)

# Regex para CNPJ (formatado ou só dígitos)
_RE_CNPJ = re.compile(
    r"\b\d{2}[. ]?\d{3}[. ]?\d{3}[/. ]?\d{4}[-. ]?\d{2}\b"
)

# Regex para datas comuns em documentos fiscais
_RE_DATA = re.compile(
    r"\b(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})\b"
)

# Regex para percentagens fiscais (alíquotas, FatorR, etc.) — ex.: 7,30% ou 9,50%
_RE_PERCENTAGEM = re.compile(r"\d+(?:[.,]\d+)?%")


def extrair_valores_monetarios(texto: str) -> list[str]:
    """Extrai todos os valores em R$ encontrados no texto."""
    return [m.group(0).strip() for m in _RE_VALOR.finditer(texto)]


def extrair_percentagens(texto: str) -> list[str]:
    """Extrai todas as percentagens do texto (alíquotas, FatorR, etc.)."""
    return [m.group(0).strip() for m in _RE_PERCENTAGEM.finditer(texto)]


def extrair_cnpjs(texto: str) -> list[str]:
    """Extrai todos os CNPJs encontrados no texto (formatados ou só dígitos)."""
    return [m.group(0).strip() for m in _RE_CNPJ.finditer(texto)]


def extrair_datas(texto: str) -> list[str]:
    """Extrai todas as datas encontradas no texto."""
    return [m.group(0).strip() for m in _RE_DATA.finditer(texto)]


def _contem_afirmacao_fiscal(texto: str) -> bool:
    """Retorna True se o texto contém pelo menos uma afirmação fiscal verificável.

    Uma afirmação fiscal é qualquer ocorrência de valor monetário (R$), data,
    CNPJ ou percentagem. Textos puramente conversacionais sem esses elementos
    (ex.: "Olá!", "Não tenho essa informação") não são afirmações fiscais e
    não acionam o gate de citação obrigatória.
    """
    return bool(
        extrair_valores_monetarios(texto)
        or extrair_percentagens(texto)
        or extrair_cnpjs(texto)
        or extrair_datas(texto)
    )


def validar_resposta(resp: LLMResponse, fontes: list[FonteFato]) -> bool:
    """
    Re-check determinístico pós-LLM (§8.5 + §8.6 do Plano).

    Regra 1: Toda citação deve referenciar um fato_id que existe nas fontes.
    Regra 2: Todo valor monetário (R$) no texto deve aparecer literalmente no payload de alguma fonte.
    Regra 2b: Toda percentagem (alíquota, FatorR) deve aparecer literalmente no payload de alguma fonte.
    Regra 3: Todo CNPJ no texto deve aparecer literalmente no payload de alguma fonte.
    Regra 4: Toda data no texto deve aparecer literalmente no payload de alguma fonte.
    Regra 5 (§8.5): Se há fontes disponíveis E o texto contém afirmação fiscal verificável,
                    exige ≥1 citação com fato_id válido. Impede que resposta fiscal passe
                    sem nenhuma âncora ao grafo — o caso central do achado #4.

    Retorna False em qualquer violação → caller usa RESPOSTA_PADRAO_VERIFICAR.
    """
    ids_validos = {f.id for f in fontes}
    payloads = " ".join(f.payload for f in fontes)

    # Regra 1: toda citação tem ID válido
    for cit in resp.citacoes:
        if cit.fato_id not in ids_validos:
            return False

    # Regra 2: todo valor monetário aparece nas fontes
    for valor in extrair_valores_monetarios(resp.texto):
        # Normaliza espaços para comparação
        valor_norm = re.sub(r"\s+", " ", valor).strip()
        if valor_norm not in payloads:
            return False

    # Regra 2b: toda percentagem (alíquota, FatorR) aparece nas fontes
    for pct in extrair_percentagens(resp.texto):
        if pct not in payloads:
            return False

    # Regra 3: todo CNPJ aparece nas fontes
    for cnpj in extrair_cnpjs(resp.texto):
        cnpj_digits = re.sub(r"[^\d]", "", cnpj)
        # Busca tanto o CNPJ formatado quanto só dígitos nos payloads
        if cnpj not in payloads and cnpj_digits not in payloads:
            return False

    # Regra 4: toda data aparece nas fontes
    for data in extrair_datas(resp.texto):
        if data not in payloads:
            return False

    # Regra 5 (§8.5): citação obrigatória quando há afirmação fiscal + fontes disponíveis.
    # Aplica-se apenas quando fontes existem (sem fontes o assistente já sinaliza ao usuário
    # que não há dados — não faz sentido exigir citação de grafo vazio).
    # Não-afirmações (saudações, "não sei", orientações genéricas) passam sem citação.
    return not (fontes and _contem_afirmacao_fiscal(resp.texto) and len(resp.citacoes) == 0)


def detectar_out_of_scope(pergunta: str) -> tuple[bool, str | None]:
    """
    Detecta se uma pergunta deve ser encaminhada ao marketplace de contadores.

    Usa pattern matching determinístico contra OUT_OF_SCOPE_PATTERNS.
    Para casos ambíguos, o LLMClient pode chamar Gemma 3 4B local (Sprint 4).

    Retorna (True, categoria) se out-of-scope, (False, None) caso contrário.
    """
    pergunta_lower = pergunta.lower()
    for categoria, padroes in OUT_OF_SCOPE_PATTERNS.items():
        for padrao in padroes:
            if padrao in pergunta_lower:
                return True, categoria
    return False, None
