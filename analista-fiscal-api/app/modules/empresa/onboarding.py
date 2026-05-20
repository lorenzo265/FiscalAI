"""Lógica pura de onboarding: CNPJ → regime tributário provável.

Regras baseadas em LC 123/2006 e RFB:
  MEI      : porte='MEI' ou faturamento <= 81_000/ano
  Simples  : porte 'ME' | 'EPP', faturamento <= 4_800_000/ano e CNAE permitido
  LP       : faturamento > 4_800_000 até 78_000_000, ou CNAE vedado ao SN
  LR       : faturamento > 78_000_000 (não determinável sem análise; LP como default)

Zero I/O — pure function. Testável sem banco ou rede.
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.empresa.schemas import AnexoSimples, RegimeTributario

_LIMITE_MEI = Decimal("81000.00")
# MEI Caminhoneiro / Transportador Autônomo de Carga — LC 188/2021.
_LIMITE_MEI_TRANSPORTADOR = Decimal("251600.00")
_LIMITE_SN = Decimal("4_800_000.00")

# CNAEs admitidos para MEI Caminhoneiro (Resolução CGSN 140/2018 alterada).
_CNAES_MEI_TRANSPORTADOR: frozenset[str] = frozenset(
    {
        "4930201",  # Transporte rodoviário de carga municipal, exceto produtos perigosos e mudanças
        "4930202",  # Transporte rodoviário de carga intermunicipal, interestadual e internacional
        "4930203",  # Transporte rodoviário de produtos perigosos
        "4930204",  # Transporte rodoviário de mudanças
    }
)

# CNAEs vedados ao Simples Nacional (LC 123/2006 art. 17 e IN RFB 2082/2022).
# Lista não exaustiva; verificar obrigação específica no Portal do Simples Nacional.
_CNAES_VEDADOS_SN: frozenset[str] = frozenset(
    {
        # Instituições financeiras e assemelhadas (art. 17, I-II e §3°)
        "6411300",  # Banco central
        "6421200",  # Bancos cooperativos
        "6422100",  # Banco múltiplo com carteira comercial
        "6423900",  # Banco múltiplo sem carteira comercial
        "6424701",  # Banco comercial
        "6424702",  # Banco comercial cooperativo
        "6431000",  # Banco de câmbio
        "6432800",  # Bancos de investimento
        "6433600",  # Bancos de desenvolvimento
        "6434400",  # Agências de fomento
        "6435201",  # Crédito imobiliário
        "6436100",  # Soc. de crédito, financiamento e investimento
        "6437900",  # Soc. de crédito ao microempreendedor
        "6438701",  # Bancos de câmbio e outras inst. financeiras
        "6450600",  # Sociedade de crédito
        "6461100",  # Holdings de instituições financeiras
        "6462000",  # Holdings de instituições não-financeiras
        "6470101",  # Fundos de investimento — ações e renda fixa
        "6470102",  # Fundos de investimento — multiportfólio
        "6491300",  # Factoring (cessão de créditos)
        "6492100",  # Securitizadoras de créditos imobiliários
        "6493000",  # Administração de consórcios
        "6499999",  # Outras atividades financeiras não especificadas
        "6511102",  # Planos de saúde (seguradoras)
        "6512000",  # Seguros de vida
        "6520100",  # Seguros não-vida
        "6530800",  # Resseguradores
        "6541300",  # Previdência complementar fechada
        "6542100",  # Previdência complementar aberta
        "6550200",  # Planos de saúde (operadoras)
        "6611801",  # Bolsa de valores
        "6611802",  # Bolsa de mercadorias
        "6612601",  # Corretoras de títulos e valores mobiliários
        "6612602",  # Distribuidoras de títulos e valores mobiliários
        "6613400",  # Administração de cartões de crédito
        "6619301",  # Câmbio, títulos e metais (não bancário)
        "6619302",  # Correspondentes bancários
        "6619399",  # Outras atividades auxiliares financeiras
        "6621501",  # Seguradoras — avaliação de riscos
        "6621502",  # Seguradoras — inspetores de riscos
        "6622300",  # Corretores e agentes de seguros
        "6629100",  # Atividades auxiliares dos seguros
        "6630400",  # Previdência complementar — administradoras
        # Geração/transmissão/distribuição de energia (art. 17, IV LC 123/2006)
        "3511500",  # Geração de energia elétrica
        "3512300",  # Transmissão de energia elétrica
        "3513100",  # Comércio atacadista de energia elétrica
        "3514000",  # Distribuição de energia elétrica
        # Importação/exportação de combustíveis (art. 17, VIII)
        "4681801",  # Comércio atacadista de álcool carburante
        "4681802",  # Comércio atacadista de combustíveis exceto álcool
        # Fabricação/comércio de armas e munições (art. 17, VIII)
        "2520400",  # Fabricação de armas de fogo e munições
        "4763602",  # Comércio varejista de armas e munições
        # Segurança privada (art. 17, VI — vigilância, segurança, transporte valores)
        "8011101",  # Atividades de vigilância e segurança privada
        "8011102",  # Serviço de escolta — segurança privada
        "8012900",  # Atividades de transporte de valores
        # Gestão e administração de participações societárias (holdings)
        "6420100",  # Atividades de soc. de participação — holdings
        # Planos de saúde — operadoras com fins lucrativos
        "6550200",  # Planos de saúde (operadoras — já listado acima, duplicata segura)
        # Cessão / locação de mão-de-obra (art. 17, XII LC 123/2006)
        "7820500",  # Locação de mão-de-obra temporária
        # Loteamento e incorporação de imóveis (art. 17, XIV)
        "4110700",  # Incorporação de empreendimentos imobiliários
        "6810203",  # Loteamento de imóveis próprios
        # Produção / atacado de bebidas alcoólicas e cigarros (art. 17, X)
        # OBS: micro e pequenas cervejarias têm exceção (LC 155/2016) — tratada fora do CNAE.
        "1111901",  # Fabricação de aguardente de cana-de-açúcar
        "1111902",  # Fabricação de outras aguardentes e bebidas destiladas
        "1112700",  # Fabricação de vinho
        "1113502",  # Fabricação de cervejas e chopes (verificar exceção LC 155/2016)
        "1220401",  # Fabricação de cigarros
        "1220499",  # Fabricação de outros produtos do fumo
        "4635401",  # Comércio atacadista de água mineral
        "4635499",  # Comércio atacadista de bebidas com atividade de fracionamento
        "4636201",  # Comércio atacadista de fumo beneficiado
        "4636202",  # Comércio atacadista de cigarros, cigarrilhas e charutos
        # NOTA: Advocacia (6911701), Contabilidade (6920602) e demais profissões
        # regulamentadas SÃO permitidas no Simples Nacional sob o Anexo IV ou V
        # (LC 147/2014). Não incluir aqui.
    }
)

# CNAEs tipicamente associados ao Anexo III (serviços com Fator R)
_CNAES_ANEXO_III: frozenset[str] = frozenset(
    {
        "6201501",  # Desenvolvimento de programas de computador
        "6202300",  # Desenvolvimento de software
        "6209100",  # Suporte técnico em TI
        "7410202",  # Design gráfico
        "7490103",  # Consultoria em gestão
        "6911701",  # Advocacia
        "6920602",  # Contabilidade
        "7111100",  # Arquitetura
        "7112000",  # Engenharia
        "8630501",  # Clínica médica
        "8630502",  # Clínica odontológica
    }
)


def derivar_regime_por_porte(
    porte: str,
    faturamento_anual: Decimal | None,
    cnae_principal: str | None = None,
) -> RegimeTributario:
    """Deriva o regime tributário mais provável dado porte BrasilAPI + faturamento.

    Args:
        porte: Campo `porte` da BrasilAPI — "MEI", "ME", "EPP" ou "DEMAIS".
        faturamento_anual: Receita bruta anual declarada (ou None se desconhecida).
        cnae_principal: CNAE sem pontuação (7 dígitos) para detectar vedações ao SN.

    Returns:
        RegimeTributario mais provável (conservador: LP quando incerto entre LP/LR).
    """
    porte_upper = porte.upper() if porte else ""
    fat = faturamento_anual or Decimal("0")
    cnae7 = cnae_principal[:7] if cnae_principal else None
    is_transportador = cnae7 in _CNAES_MEI_TRANSPORTADOR if cnae7 else False

    if porte_upper == "MEI":
        # MEI Caminhoneiro tem limite ampliado (LC 188/2021): R$251.600.
        if is_transportador and fat <= _LIMITE_MEI_TRANSPORTADOR:
            return RegimeTributario.MEI
        if not is_transportador and fat <= _LIMITE_MEI:
            return RegimeTributario.MEI
        # Estourou o teto MEI — empresa precisa ser desenquadrada.
        # Cai no fluxo de SN/LP abaixo, como se porte fosse "ME".

    cnae_vedado = cnae_principal in _CNAES_VEDADOS_SN if cnae_principal else False

    # Trata "MEI que estourou" como "ME" para fins de classificação SN vs LP.
    porte_efetivo = "ME" if porte_upper == "MEI" else porte_upper

    if not cnae_vedado and fat <= _LIMITE_SN and porte_efetivo in {"ME", "EPP", ""}:
        return RegimeTributario.SIMPLES_NACIONAL

    return RegimeTributario.LUCRO_PRESUMIDO


def sugerir_anexo_simples(cnae_principal: str | None) -> AnexoSimples | None:
    """Sugere o anexo do Simples Nacional mais provável pelo CNAE.

    Retorna None se não for possível sugerir (usuário deve informar manualmente).
    Baseado na tabela de atividades econômicas da LC 123/2006.
    """
    if cnae_principal is None:
        return None

    cnae7 = cnae_principal.replace(".", "").replace("-", "").replace("/", "")[:7]

    if cnae7 in _CNAES_ANEXO_III:
        return AnexoSimples.III

    divisao = cnae7[:2] if len(cnae7) >= 2 else ""

    # Comércio varejista/atacadista → Anexo I
    if divisao in {"45", "46", "47"}:
        return AnexoSimples.I

    # Indústria de transformação → Anexo II
    if divisao in {str(d) for d in range(10, 33)}:
        return AnexoSimples.II

    # Serviços profissionais regulamentados → Anexo IV ou V
    if divisao in {"69", "70", "71", "72", "73", "74", "75"}:
        return AnexoSimples.IV

    return None


def mapear_dados_brasil_api(dados: dict[str, object]) -> dict[str, object]:
    """Extrai e normaliza campos relevantes do payload da BrasilAPI.

    Retorna apenas os campos usados no onboarding.
    """
    cnae_list = dados.get("cnaes_secundarios") or []
    cnae_principal_raw = dados.get("cnae_fiscal_descricao")

    cnae_codigo = str(dados.get("cnae_fiscal", "")).replace(".", "").replace("-", "")

    return {
        "razao_social": str(dados.get("razao_social", "")),
        "nome_fantasia": str(dados.get("nome_fantasia", "")) or None,
        "porte": str(dados.get("porte", "")),
        "cnae_principal": cnae_codigo[:7] if cnae_codigo else None,
        "cnae_descricao": str(cnae_principal_raw) if cnae_principal_raw else None,
        "municipio": str(dados.get("municipio", "")) or None,
        "uf": str(dados.get("uf", "")) or None,
        "situacao": str(dados.get("descricao_situacao_cadastral", "")),
    }
