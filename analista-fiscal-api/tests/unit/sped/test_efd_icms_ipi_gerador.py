"""Testes do gerador EFD ICMS-IPI (Sprint 17 PR2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.sped.compartilhado import contar_registros
from app.modules.sped.efd.gerador_icms_ipi import (
    ALGORITMO_VERSAO,
    ApuracaoMensalIcms,
    ApuracaoMensalIpi,
    DocumentoIcmsEfd,
    EntradaEfdIcmsIpi,
    IdentificacaoEmpresaEfdIcms,
    ObrigacaoIcmsRecolher,
    ParticipanteIcms,
    _EntradaEfdIcmsInvalida,
    gerar_efd_icms_ipi,
)
from app.modules.sped.validador import validar_efd_icms_ipi


# ── Fixtures de entrada ─────────────────────────────────────────────────────


def _empresa_sp() -> IdentificacaoEmpresaEfdIcms:
    return IdentificacaoEmpresaEfdIcms(
        cnpj="12345678000190",
        razao_social="Comércio SP LTDA",
        nome_fantasia="Modelo",
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
        inscricao_estadual="111222333",
    )


def _participante() -> ParticipanteIcms:
    return ParticipanteIcms(
        codigo="99887766000155",
        nome="Cliente Fictício LTDA",
        cnpj="99887766000155",
    )


def _apuracao_devedor() -> ApuracaoMensalIcms:
    """Mês com R$ 9.000 a recolher (50.000 × 18%)."""
    return ApuracaoMensalIcms(
        valor_total_debitos=Decimal("9000.00"),
        valor_total_creditos=Decimal("0"),
        saldo_credor_anterior=Decimal("0"),
        ajustes_devedores=Decimal("0"),
        ajustes_credores=Decimal("0"),
        valor_icms_a_recolher=Decimal("9000.00"),
        saldo_credor_a_transportar=Decimal("0"),
    )


def _apuracao_credor() -> ApuracaoMensalIcms:
    """Mês com saldo credor acumulado — sem ICMS a recolher."""
    return ApuracaoMensalIcms(
        valor_total_debitos=Decimal("1000.00"),
        valor_total_creditos=Decimal("3000.00"),
        saldo_credor_anterior=Decimal("0"),
        ajustes_devedores=Decimal("0"),
        ajustes_credores=Decimal("0"),
        valor_icms_a_recolher=Decimal("0"),
        saldo_credor_a_transportar=Decimal("2000.00"),
    )


def _doc_nfe_venda(*, numero: str = "1001") -> DocumentoIcmsEfd:
    """NF-e venda interna SP — R$ 50.000 com 18% de ICMS."""
    return DocumentoIcmsEfd(
        chave="35260612345678000190550010000010011000000010",
        numero=numero,
        serie="1",
        modelo="55",
        data_emissao=date(2026, 3, 5),
        codigo_participante="99887766000155",
        valor_total=Decimal("50000.00"),
        valor_mercadorias=Decimal("50000.00"),
        valor_icms=Decimal("9000.00"),
        aliquota_icms=Decimal("18.00"),
        cfop="5102",
        cst_icms="000",
        ncm="22030000",
    )


def _entrada_minima(
    *,
    documentos: tuple[DocumentoIcmsEfd, ...] = (),
    apuracao: ApuracaoMensalIcms | None = None,
    obrigacoes: tuple[ObrigacaoIcmsRecolher, ...] = (),
    apuracao_ipi: ApuracaoMensalIpi | None = None,
) -> EntradaEfdIcmsIpi:
    return EntradaEfdIcmsIpi(
        empresa=_empresa_sp(),
        competencia_inicio=date(2026, 3, 1),
        competencia_fim=date(2026, 3, 31),
        apuracao_icms=apuracao or _apuracao_devedor(),
        participantes=(_participante(),),
        documentos=documentos,
        obrigacoes_a_recolher=obrigacoes,
        apuracao_ipi=apuracao_ipi or ApuracaoMensalIpi(preenchido=False),
    )


# ── Caso 1 — Comércio SP com saldo devedor ──────────────────────────────────


class TestComercioSpSaldoDevedor:
    def test_gera_arquivo_com_blocos_e_hash(self) -> None:
        entrada = _entrada_minima(
            documentos=(_doc_nfe_venda(),),
            obrigacoes=(
                ObrigacaoIcmsRecolher(
                    codigo_obrigacao="000",
                    valor=Decimal("9000.00"),
                    data_vencimento=date(2026, 4, 10),
                ),
            ),
        )
        out = gerar_efd_icms_ipi(entrada)
        assert out.algoritmo_versao == ALGORITMO_VERSAO
        assert out.tamanho_bytes == len(out.conteudo)
        assert len(out.hash_sha256) == 64

        texto = out.conteudo.decode("latin-1")
        assert texto.startswith("|0000|")
        for ln in texto.splitlines():
            assert ln.startswith("|") and ln.endswith("|")

        regs = contar_registros(texto.splitlines())
        # Blocos obrigatórios completos.
        for prefixo in ("0", "C", "D", "E", "G", "H", "1", "9"):
            assert regs.get(f"{prefixo}001", 0) == 1
            assert regs.get(f"{prefixo}990", 0) == 1
        # Documento gerou C100/C170/C190 + E110/E116.
        assert regs.get("C100") == 1
        assert regs.get("C170") == 1
        assert regs.get("C190") == 1
        assert regs.get("E100") == 1
        assert regs.get("E110") == 1
        assert regs.get("E116") == 1

    def test_validador_aceita_arquivo_perfeito(self) -> None:
        entrada = _entrada_minima(documentos=(_doc_nfe_venda(),))
        out = gerar_efd_icms_ipi(entrada)
        resultado = validar_efd_icms_ipi(out.conteudo.decode("latin-1"))
        assert resultado.ok, [e.codigo for e in resultado.erros]


# ── Caso 2 — Indústria com IPI ──────────────────────────────────────────────


class TestIndustriaComIpi:
    def test_bloco_e200_e210_preenchidos_quando_ipi_ativo(self) -> None:
        ipi = ApuracaoMensalIpi(
            preenchido=True,
            valor_total_debitos=Decimal("1500.00"),
            valor_total_creditos=Decimal("500.00"),
            saldo_credor_anterior=Decimal("0"),
            valor_ipi_a_recolher=Decimal("1000.00"),
            saldo_credor_a_transportar=Decimal("0"),
        )
        entrada = _entrada_minima(
            documentos=(_doc_nfe_venda(),),
            apuracao_ipi=ipi,
        )
        out = gerar_efd_icms_ipi(entrada)
        texto = out.conteudo.decode("latin-1")
        regs = contar_registros(texto.splitlines())
        assert regs.get("E200") == 1
        assert regs.get("E210") == 1

    def test_e200_ausente_quando_ipi_nao_preenchido(self) -> None:
        entrada = _entrada_minima(documentos=(_doc_nfe_venda(),))
        out = gerar_efd_icms_ipi(entrada)
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines())
        assert regs.get("E200", 0) == 0
        assert regs.get("E210", 0) == 0


# ── Caso 3 — Mês com saldo credor anterior + sem ICMS a recolher ───────────


class TestSaldoCredor:
    def test_saldo_credor_a_transportar_em_e110(self) -> None:
        entrada = _entrada_minima(apuracao=_apuracao_credor())
        out = gerar_efd_icms_ipi(entrada)
        texto = out.conteudo.decode("latin-1")
        # E110: VL_SLD_CREDOR_TRANSPORTAR é o 13º campo (índice 12 de campos).
        for ln in texto.splitlines():
            if ln.startswith("|E110|"):
                campos = ln.strip().split("|")[2:-1]
                # campos[11] = VL_ICMS_RECOLHER, campos[12] = VL_SLD_CREDOR_TRANSPORTAR
                assert campos[11] == "0,00"
                assert campos[12] == "2000,00"
                break
        else:
            pytest.fail("E110 não encontrado no arquivo gerado")

    def test_sem_obrigacao_e116_quando_credor(self) -> None:
        entrada = _entrada_minima(apuracao=_apuracao_credor())
        out = gerar_efd_icms_ipi(entrada)
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines())
        # Service só gera E116 quando icms_a_recolher > 0; mas o gerador puro
        # respeita o que vem em entrada.obrigacoes_a_recolher (vazia aqui).
        assert regs.get("E116", 0) == 0


# ── Caso 4 — Pré-condições inválidas ───────────────────────────────────────


class TestPreCondicoes:
    def test_cnpj_invalido(self) -> None:
        emp = IdentificacaoEmpresaEfdIcms(
            cnpj="123",
            razao_social="X",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="3550308",
            inscricao_estadual="111",
        )
        entrada = EntradaEfdIcmsIpi(
            empresa=emp,
            competencia_inicio=date(2026, 3, 1),
            competencia_fim=date(2026, 3, 31),
            apuracao_icms=_apuracao_devedor(),
        )
        with pytest.raises(_EntradaEfdIcmsInvalida, match="CNPJ"):
            gerar_efd_icms_ipi(entrada)

    def test_ie_vazia_eh_erro(self) -> None:
        emp = IdentificacaoEmpresaEfdIcms(
            cnpj="12345678000190",
            razao_social="X",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="3550308",
            inscricao_estadual="",
        )
        entrada = EntradaEfdIcmsIpi(
            empresa=emp,
            competencia_inicio=date(2026, 3, 1),
            competencia_fim=date(2026, 3, 31),
            apuracao_icms=_apuracao_devedor(),
        )
        with pytest.raises(_EntradaEfdIcmsInvalida, match="[Ii]nscrição estadual"):
            gerar_efd_icms_ipi(entrada)

    def test_competencia_diferente_de_um_mes_eh_erro(self) -> None:
        entrada = EntradaEfdIcmsIpi(
            empresa=_empresa_sp(),
            competencia_inicio=date(2026, 3, 1),
            competencia_fim=date(2026, 4, 30),
            apuracao_icms=_apuracao_devedor(),
        )
        with pytest.raises(_EntradaEfdIcmsInvalida, match="mensal"):
            gerar_efd_icms_ipi(entrada)

    def test_cfop_invalido(self) -> None:
        doc = DocumentoIcmsEfd(
            chave="35260612345678000190550010000010011000000010",
            numero="1001",
            serie="1",
            modelo="55",
            data_emissao=date(2026, 3, 5),
            codigo_participante="99887766000155",
            valor_total=Decimal("50000.00"),
            valor_mercadorias=Decimal("50000.00"),
            valor_icms=Decimal("9000.00"),
            aliquota_icms=Decimal("18.00"),
            cfop="ABC",
        )
        entrada = _entrada_minima(documentos=(doc,))
        with pytest.raises(_EntradaEfdIcmsInvalida, match="CFOP"):
            gerar_efd_icms_ipi(entrada)

    def test_cst_icms_com_2_digitos_eh_erro(self) -> None:
        doc = DocumentoIcmsEfd(
            chave="35260612345678000190550010000010011000000010",
            numero="1001",
            serie="1",
            modelo="55",
            data_emissao=date(2026, 3, 5),
            codigo_participante="99887766000155",
            valor_total=Decimal("50000.00"),
            valor_mercadorias=Decimal("50000.00"),
            valor_icms=Decimal("9000.00"),
            aliquota_icms=Decimal("18.00"),
            cfop="5102",
            cst_icms="00",  # 2 dígitos — inválido (espera 3)
        )
        entrada = _entrada_minima(documentos=(doc,))
        with pytest.raises(_EntradaEfdIcmsInvalida, match="CST ICMS"):
            gerar_efd_icms_ipi(entrada)


# ── Bloco G — CIAP (Sprint 19.6 PR1 #31) ───────────────────────────────────


from app.modules.sped.efd.ciap import (  # noqa: E402
    MovimentoCiap,
    SnapshotCiap,
)


class TestBlocoGCiap:
    def test_sem_ciap_emite_bloco_g_vazio(self) -> None:
        """``entrada.ciap=None`` (default) → G001(IND_MOV=1)+G990 apenas."""
        entrada = _entrada_minima(documentos=(_doc_nfe_venda(),))
        gerado = gerar_efd_icms_ipi(entrada)
        conteudo = gerado.conteudo.decode("latin-1")
        # G001 com IND_MOV=1 (sem dados) + G990 imediato.
        assert "|G001|1|" in conteudo
        assert "|G110|" not in conteudo
        assert "|G125|" not in conteudo
        assert "|G990|" in conteudo

    def test_com_ciap_emite_g110_e_g125(self) -> None:
        """Snapshot com 1 movimento → G110(saldo)+G125(linha)+G990."""
        snap = SnapshotCiap(
            saldo_inicial_icms=Decimal("4800.00"),
            soma_parcelas_periodo=Decimal("100.00"),
            saldo_final_icms=Decimal("4700.00"),
            movimentos=(
                MovimentoCiap(
                    bem_id="bem-001",
                    data_movimento=date(2026, 3, 31),
                    tipo_movimento="IM",
                    valor_imob_icms_op=Decimal("4800.00"),
                    num_parcela=1,
                    valor_parcela=Decimal("100.00"),
                ),
            ),
        )
        entrada = EntradaEfdIcmsIpi(
            empresa=_empresa_sp(),
            competencia_inicio=date(2026, 3, 1),
            competencia_fim=date(2026, 3, 31),
            apuracao_icms=_apuracao_devedor(),
            participantes=(_participante(),),
            documentos=(_doc_nfe_venda(),),
            obrigacoes_a_recolher=(
                ObrigacaoIcmsRecolher(
                    codigo_obrigacao="000",
                    valor=Decimal("9000.00"),
                    data_vencimento=date(2026, 4, 10),
                ),
            ),
            ciap=snap,
        )
        gerado = gerar_efd_icms_ipi(entrada)
        conteudo = gerado.conteudo.decode("latin-1")
        # G001 com IND_MOV=0 (com dados).
        assert "|G001|0|" in conteudo
        # G110 — saldo inicial + parcelas + saldo final.
        assert "|G110|" in conteudo
        assert "|4800,00|100,00|" in conteudo  # SALDO_IN_ICMS|SOM_PARC
        assert "|4700,00|" in conteudo  # SALDO_FN_ICMS
        # G125 — movimento com num_parcela=1 e valor_parcela=100.
        assert "|G125|bem-001|" in conteudo
        assert "|IM|" in conteudo
        assert "|1|100,00|" in conteudo  # NUM_PARC|VL_PARC_PASS
        # G990 final.
        assert "|G990|" in conteudo


# ── Determinismo ────────────────────────────────────────────────────────────


class TestDeterminismo:
    def test_mesmo_input_gera_mesmo_hash(self) -> None:
        entrada = _entrada_minima(documentos=(_doc_nfe_venda(),))
        a = gerar_efd_icms_ipi(entrada)
        b = gerar_efd_icms_ipi(entrada)
        assert a.hash_sha256 == b.hash_sha256
