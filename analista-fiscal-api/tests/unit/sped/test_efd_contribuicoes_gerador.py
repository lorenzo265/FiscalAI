"""Testes do gerador EFD-Contribuições (Sprint 17 PR1).

Estratégia: gera arquivos completos a partir de DTOs canônicos e verifica:

1. Estrutura pipe-delimited íntegra (todas as linhas com pipe inicial/final).
2. Cada bloco com abertura ``X001`` + encerramento ``X990``.
3. Registro ``9999`` igual ao total real de linhas.
4. Cada ``9900`` declarando contagem real do seu tipo.
5. Casos de pré-condição inválida abortam com ``_EntradaEfdInvalida``.
6. Caso golden: gerador puro passa o validador local sem erros.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.sped.compartilhado import contar_registros
from app.modules.sped.efd.gerador_contribuicoes import (
    ALGORITMO_VERSAO,
    ApuracaoMensalPisCofins,
    DocumentoMercadoriaEfd,
    DocumentoServicoEfd,
    EntradaEfdContribuicoes,
    IdentificacaoEmpresaEfd,
    ParticipanteEfd,
    _EntradaEfdInvalida,
    gerar_efd_contribuicoes,
)
from app.modules.sped.validador import validar_efd_contribuicoes


# ── Fixtures de entrada mínima ──────────────────────────────────────────────


def _empresa() -> IdentificacaoEmpresaEfd:
    return IdentificacaoEmpresaEfd(
        cnpj="12345678000190",
        razao_social="Comércio Modelo LTDA",
        nome_fantasia="Modelo",
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
        cep="01310100",
        email="contato@modelo.com.br",
        telefone="1133334444",
        inscricao_estadual="111222333",
        inscricao_municipal="987654",
    )


def _participante_cliente() -> ParticipanteEfd:
    return ParticipanteEfd(
        codigo="99887766000155",
        nome="Cliente Fictício LTDA",
        cnpj="99887766000155",
    )


def _apuracao_canonica() -> ApuracaoMensalPisCofins:
    """LP com R$ 100.000 de receita no mês → PIS 650 + Cofins 3.000."""
    return ApuracaoMensalPisCofins(
        base_calculo_pis=Decimal("100000.00"),
        aliquota_pis=Decimal("0.65"),
        valor_pis_apurado=Decimal("650.00"),
        valor_pis_a_recolher=Decimal("650.00"),
        base_calculo_cofins=Decimal("100000.00"),
        aliquota_cofins=Decimal("3.00"),
        valor_cofins_apurado=Decimal("3000.00"),
        valor_cofins_a_recolher=Decimal("3000.00"),
    )


def _doc_mercadoria(*, numero: str = "1001") -> DocumentoMercadoriaEfd:
    """NF-e venda interna SP — R$ 50.000."""
    return DocumentoMercadoriaEfd(
        chave="35250612345678000190550010000010011000000010",
        numero=numero,
        serie="1",
        modelo="55",
        data_emissao=date(2026, 3, 5),
        codigo_participante="99887766000155",
        valor_total=Decimal("50000.00"),
        valor_mercadorias=Decimal("50000.00"),
        valor_pis=Decimal("325.00"),
        valor_cofins=Decimal("1500.00"),
        aliquota_pis=Decimal("0.65"),
        aliquota_cofins=Decimal("3.00"),
        cfop="5102",
        ncm="22030000",
    )


def _doc_servico() -> DocumentoServicoEfd:
    """NFS-e prestação de serviço — R$ 50.000."""
    return DocumentoServicoEfd(
        chave=None,
        numero="42",
        serie="A",
        data_emissao=date(2026, 3, 10),
        codigo_participante="99887766000155",
        valor_total=Decimal("50000.00"),
        valor_servicos=Decimal("50000.00"),
        valor_pis=Decimal("325.00"),
        valor_cofins=Decimal("1500.00"),
        aliquota_pis=Decimal("0.65"),
        aliquota_cofins=Decimal("3.00"),
    )


def _entrada_minima(
    *,
    servicos: tuple[DocumentoServicoEfd, ...] = (),
    mercadorias: tuple[DocumentoMercadoriaEfd, ...] = (),
    apuracao: ApuracaoMensalPisCofins | None = None,
) -> EntradaEfdContribuicoes:
    return EntradaEfdContribuicoes(
        empresa=_empresa(),
        competencia_inicio=date(2026, 3, 1),
        competencia_fim=date(2026, 3, 31),
        apuracao=apuracao or _apuracao_canonica(),
        participantes=(_participante_cliente(),),
        servicos=servicos,
        mercadorias=mercadorias,
    )


# ── Caso 1 — LP só com NF-e ─────────────────────────────────────────────────


class TestLpSoMercadoria:
    def test_gera_arquivo_com_blocos_e_hash(self) -> None:
        entrada = _entrada_minima(mercadorias=(_doc_mercadoria(),))
        out = gerar_efd_contribuicoes(entrada)
        assert out.algoritmo_versao == ALGORITMO_VERSAO
        assert out.tamanho_bytes == len(out.conteudo)
        assert len(out.hash_sha256) == 64
        assert out.total_linhas > 10

        texto = out.conteudo.decode("latin-1")
        # 0000 abre, 9999 fecha, todas as linhas têm pipe nas pontas.
        assert texto.startswith("|0000|")
        assert texto.rstrip().endswith("|")
        for ln in texto.splitlines():
            assert ln.startswith("|") and ln.endswith("|")

        regs = contar_registros(texto.splitlines())
        # Blocos obrigatórios — abertura e encerramento únicos.
        for prefixo in ("0", "A", "C", "D", "F", "M", "1", "9"):
            assert regs.get(f"{prefixo}001", 0) == 1, (
                f"{prefixo}001 faltando: {regs}"
            )
            assert regs.get(f"{prefixo}990", 0) == 1, (
                f"{prefixo}990 faltando: {regs}"
            )

    def test_validador_aceita_arquivo_perfeito(self) -> None:
        entrada = _entrada_minima(mercadorias=(_doc_mercadoria(),))
        out = gerar_efd_contribuicoes(entrada)
        resultado = validar_efd_contribuicoes(out.conteudo.decode("latin-1"))
        assert resultado.ok, f"erros: {[e.codigo for e in resultado.erros]}"


# ── Caso 2 — LP com NF-e + NFS-e mistas ────────────────────────────────────


class TestLpMisto:
    def test_blocos_a_e_c_ambos_com_dados(self) -> None:
        entrada = _entrada_minima(
            servicos=(_doc_servico(),),
            mercadorias=(_doc_mercadoria(),),
        )
        out = gerar_efd_contribuicoes(entrada)
        texto = out.conteudo.decode("latin-1")
        regs = contar_registros(texto.splitlines())
        # Cabeçalhos de documento (A100/C100), itens (A170/C170) e
        # identificação de estabelecimento (A010/C010) presentes.
        assert regs.get("A010") == 1
        assert regs.get("A100") == 1
        assert regs.get("A170") == 1
        assert regs.get("C010") == 1
        assert regs.get("C100") == 1
        assert regs.get("C170") == 1
        # Bloco D / F / 1 ficam sem dados → IND_MOV=1 + abertura+encerramento.
        assert regs.get("D001") == 1
        assert regs.get("D990") == 1
        assert regs.get("F001") == 1
        assert regs.get("F990") == 1


# ── Caso 3 — Mês sem movimento (só apuração) ───────────────────────────────


class TestMesSemMovimento:
    def test_arquivo_minimo_valido_quando_nao_ha_documentos(self) -> None:
        apuracao_zerada = ApuracaoMensalPisCofins(
            base_calculo_pis=Decimal("0"),
            aliquota_pis=Decimal("0.65"),
            valor_pis_apurado=Decimal("0"),
            valor_pis_a_recolher=Decimal("0"),
            base_calculo_cofins=Decimal("0"),
            aliquota_cofins=Decimal("3.00"),
            valor_cofins_apurado=Decimal("0"),
            valor_cofins_a_recolher=Decimal("0"),
        )
        entrada = _entrada_minima(apuracao=apuracao_zerada)
        out = gerar_efd_contribuicoes(entrada)
        texto = out.conteudo.decode("latin-1")
        regs = contar_registros(texto.splitlines())
        # Blocos A e C abertos como vazios.
        assert regs.get("A001") == 1
        assert regs.get("A990") == 1
        assert regs.get("A100", 0) == 0
        assert regs.get("C001") == 1
        assert regs.get("C990") == 1
        assert regs.get("C100", 0) == 0
        # M ainda obrigatório.
        assert regs.get("M200") == 1
        assert regs.get("M600") == 1
        # Validador aceita arquivo vazio coerente.
        resultado = validar_efd_contribuicoes(texto)
        assert resultado.ok, [e.codigo for e in resultado.erros]


# ── Caso 4 — pré-condições inválidas ───────────────────────────────────────


class TestPreCondicoes:
    def test_cnpj_invalido(self) -> None:
        emp = IdentificacaoEmpresaEfd(
            cnpj="123",
            razao_social="X",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="3550308",
        )
        entrada = EntradaEfdContribuicoes(
            empresa=emp,
            competencia_inicio=date(2026, 3, 1),
            competencia_fim=date(2026, 3, 31),
            apuracao=_apuracao_canonica(),
        )
        with pytest.raises(_EntradaEfdInvalida, match="CNPJ"):
            gerar_efd_contribuicoes(entrada)

    def test_municipio_ibge_invalido(self) -> None:
        emp = IdentificacaoEmpresaEfd(
            cnpj="12345678000190",
            razao_social="X",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="35503",  # < 7 dígitos
        )
        entrada = EntradaEfdContribuicoes(
            empresa=emp,
            competencia_inicio=date(2026, 3, 1),
            competencia_fim=date(2026, 3, 31),
            apuracao=_apuracao_canonica(),
        )
        with pytest.raises(_EntradaEfdInvalida, match="IBGE"):
            gerar_efd_contribuicoes(entrada)

    def test_competencia_intervalo_diferente_de_um_mes(self) -> None:
        entrada = EntradaEfdContribuicoes(
            empresa=_empresa(),
            competencia_inicio=date(2026, 3, 1),
            competencia_fim=date(2026, 4, 30),
            apuracao=_apuracao_canonica(),
        )
        with pytest.raises(_EntradaEfdInvalida, match="mensal"):
            gerar_efd_contribuicoes(entrada)

    def test_documento_referencia_participante_inexistente(self) -> None:
        doc = _doc_mercadoria()
        # Participante real não está em entrada.participantes.
        entrada = EntradaEfdContribuicoes(
            empresa=_empresa(),
            competencia_inicio=date(2026, 3, 1),
            competencia_fim=date(2026, 3, 31),
            apuracao=_apuracao_canonica(),
            participantes=(),
            mercadorias=(doc,),
        )
        with pytest.raises(_EntradaEfdInvalida, match="participante"):
            gerar_efd_contribuicoes(entrada)

    def test_cfop_invalido(self) -> None:
        doc = DocumentoMercadoriaEfd(
            chave="35250612345678000190550010000010011000000010",
            numero="1001",
            serie="1",
            modelo="55",
            data_emissao=date(2026, 3, 5),
            codigo_participante="99887766000155",
            valor_total=Decimal("50000.00"),
            valor_mercadorias=Decimal("50000.00"),
            valor_pis=Decimal("325.00"),
            valor_cofins=Decimal("1500.00"),
            aliquota_pis=Decimal("0.65"),
            aliquota_cofins=Decimal("3.00"),
            cfop="ABC",  # inválido
        )
        entrada = _entrada_minima(mercadorias=(doc,))
        with pytest.raises(_EntradaEfdInvalida, match="CFOP"):
            gerar_efd_contribuicoes(entrada)


# ── Anti-regressão FIX #7 — M200/M600 regime cumulativo ────────────────────


class TestM200M600RegimeCumulativo:
    """FIX #7 (auditoria 2026-06-04): M200/M600 campos NC devem ser zero em
    regime cumulativo; apurado e a_recolher vão nos campos CUM.

    O bug anterior gravava os valores nos campos NC_*, causando glosa no
    PVA que cruza 0110.COD_INC_TRIB="2" × M200.VL_TOT_CONT_NC_PER > 0.
    """

    def _extrair_m200(self, texto: str) -> list[str]:
        for ln in texto.splitlines():
            if ln.startswith("|M200|"):
                return ln.strip().split("|")[2:-1]  # remove pipes externos e REG
        pytest.fail("M200 não encontrado no arquivo gerado")

    def _extrair_m600(self, texto: str) -> list[str]:
        for ln in texto.splitlines():
            if ln.startswith("|M600|"):
                return ln.strip().split("|")[2:-1]
        pytest.fail("M600 não encontrado no arquivo gerado")

    def test_m200_campos_nc_sao_zero_em_cumulativo(self) -> None:
        """Campos não-cumulativos (índices 0,3,5,6) devem ser 0,00."""
        entrada = _entrada_minima(mercadorias=(_doc_mercadoria(),))
        out = gerar_efd_contribuicoes(entrada)
        campos = self._extrair_m200(out.conteudo.decode("latin-1"))
        # Layout M200: 12 campos (índices 0..11)
        # 0=VL_TOT_CONT_NC_PER, 3=VL_TOT_CONT_NC_DEV, 5=VL_OUT_DED_NC, 6=VL_CONT_NC_REC
        assert campos[0] == "0,00", f"VL_TOT_CONT_NC_PER deve ser 0,00, é {campos[0]}"
        assert campos[3] == "0,00", f"VL_TOT_CONT_NC_DEV deve ser 0,00, é {campos[3]}"
        assert campos[5] == "0,00", f"VL_OUT_DED_NC deve ser 0,00, é {campos[5]}"
        assert campos[6] == "0,00", f"VL_CONT_NC_REC deve ser 0,00, é {campos[6]}"

    def test_m200_campos_cum_recebem_apurado(self) -> None:
        """Campos cumulativos (índices 7,10,11) recebem os valores apurados."""
        ap = ApuracaoMensalPisCofins(
            base_calculo_pis=Decimal("100000.00"),
            aliquota_pis=Decimal("0.65"),
            valor_pis_apurado=Decimal("650.00"),
            valor_pis_a_recolher=Decimal("650.00"),
            base_calculo_cofins=Decimal("100000.00"),
            aliquota_cofins=Decimal("3.00"),
            valor_cofins_apurado=Decimal("3000.00"),
            valor_cofins_a_recolher=Decimal("3000.00"),
        )
        entrada = _entrada_minima(apuracao=ap)
        out = gerar_efd_contribuicoes(entrada)
        campos = self._extrair_m200(out.conteudo.decode("latin-1"))
        # 7=VL_TOT_CONT_CUM_PER (apurado), 10=VL_CONT_CUM_REC (a_recolher),
        # 11=VL_TOT_CONT_REC (total = a_recolher em regime puro cumulativo)
        assert campos[7] == "650,00", f"VL_TOT_CONT_CUM_PER deve ser 650,00, é {campos[7]}"
        assert campos[10] == "650,00", f"VL_CONT_CUM_REC deve ser 650,00, é {campos[10]}"
        assert campos[11] == "650,00", f"VL_TOT_CONT_REC deve ser 650,00, é {campos[11]}"

    def test_m600_campos_nc_sao_zero_em_cumulativo(self) -> None:
        """Mesmo que M200 — campos NC de Cofins devem ser zero em cumulativo."""
        entrada = _entrada_minima(mercadorias=(_doc_mercadoria(),))
        out = gerar_efd_contribuicoes(entrada)
        campos = self._extrair_m600(out.conteudo.decode("latin-1"))
        assert campos[0] == "0,00", f"M600 VL_TOT_CONT_NC_PER deve ser 0,00, é {campos[0]}"
        assert campos[3] == "0,00", f"M600 VL_TOT_CONT_NC_DEV deve ser 0,00, é {campos[3]}"
        assert campos[5] == "0,00", f"M600 VL_OUT_DED_NC deve ser 0,00, é {campos[5]}"
        assert campos[6] == "0,00", f"M600 VL_CONT_NC_REC deve ser 0,00, é {campos[6]}"

    def test_m600_campos_cum_recebem_apurado(self) -> None:
        """Campos cumulativos de Cofins recebem valores apurados."""
        ap = ApuracaoMensalPisCofins(
            base_calculo_pis=Decimal("100000.00"),
            aliquota_pis=Decimal("0.65"),
            valor_pis_apurado=Decimal("650.00"),
            valor_pis_a_recolher=Decimal("650.00"),
            base_calculo_cofins=Decimal("100000.00"),
            aliquota_cofins=Decimal("3.00"),
            valor_cofins_apurado=Decimal("3000.00"),
            valor_cofins_a_recolher=Decimal("3000.00"),
        )
        entrada = _entrada_minima(apuracao=ap)
        out = gerar_efd_contribuicoes(entrada)
        campos = self._extrair_m600(out.conteudo.decode("latin-1"))
        assert campos[7] == "3000,00", f"M600 VL_TOT_CONT_CUM_PER deve ser 3000,00, é {campos[7]}"
        assert campos[10] == "3000,00", f"M600 VL_CONT_CUM_REC deve ser 3000,00, é {campos[10]}"
        assert campos[11] == "3000,00", f"M600 VL_TOT_CONT_REC deve ser 3000,00, é {campos[11]}"


# ── Idempotência do hash ────────────────────────────────────────────────────


class TestDeterminismo:
    def test_mesmo_input_gera_mesmo_hash(self) -> None:
        entrada = _entrada_minima(mercadorias=(_doc_mercadoria(),))
        a = gerar_efd_contribuicoes(entrada)
        b = gerar_efd_contribuicoes(entrada)
        assert a.hash_sha256 == b.hash_sha256
        assert a.conteudo == b.conteudo
