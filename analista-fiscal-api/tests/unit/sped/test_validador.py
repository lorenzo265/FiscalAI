"""Testes do validador local SPED (Sprint 16 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.sped.ecd.gerador import (
    ContaPlano,
    EntradaEcd,
    IdentificacaoEmpresaEcd,
    LancamentoEcd,
    LinhaDemonstracao,
    PartidaLanc,
    SaldoPeriodico,
    SaldoPeriodicoConta,
    SaldoResultadoConta,
    gerar_ecd,
)
from app.modules.sped.ecf.gerador import (
    ApuracaoTrimestralLp,
    ContaPlanoEcf,
    EntradaEcf,
    IdentificacaoEmpresaEcf,
    InformacoesGerais,
    SaldoContaTrimestre,
    gerar_ecf,
)
from app.modules.sped.efd.gerador_contribuicoes import (
    ApuracaoMensalPisCofins,
    DocumentoMercadoriaEfd,
    EntradaEfdContribuicoes,
    IdentificacaoEmpresaEfd,
    ParticipanteEfd,
    gerar_efd_contribuicoes,
)
from app.modules.sped.efd.gerador_icms_ipi import (
    ApuracaoMensalIcms,
    DocumentoIcmsEfd,
    EntradaEfdIcmsIpi,
    IdentificacaoEmpresaEfdIcms,
    ParticipanteIcms,
    gerar_efd_icms_ipi,
)
from app.modules.sped.validador import (
    VALIDADOR_VERSAO,
    resultado_para_jsonb,
    validar_ecd,
    validar_ecf,
    validar_efd_contribuicoes,
    validar_efd_icms_ipi,
    validar_por_tipo,
)


# ── Fixtures: arquivos sem erros (gerados pelos próprios geradores) ────────


def _ecd_perfeita() -> str:
    """Pequena ECD perfeita gerada pelo gerador puro."""
    plano = (
        ContaPlano(
            codigo="1.1.1.01", descricao="Caixa", natureza="D", nivel=4,
            tipo_conta="A", codigo_pai=None,
            codigo_ecd_referencial="1.01.01.01.01.01",
        ),
        ContaPlano(
            codigo="4.1.01", descricao="Receita", natureza="C", nivel=3,
            tipo_conta="A", codigo_pai=None,
            codigo_ecd_referencial="4.01.01.01.01.01",
        ),
    )
    lanc = LancamentoEcd(
        numero="1",
        data=date(2025, 3, 15),
        valor_total=Decimal("1000.00"),
        indicador_origem="N",
        partidas=(
            PartidaLanc(
                codigo_conta="1.1.1.01", valor=Decimal("1000.00"),
                indicador_dc="D", historico="x",
            ),
            PartidaLanc(
                codigo_conta="4.1.01", valor=Decimal("1000.00"),
                indicador_dc="C", historico="x",
            ),
        ),
    )
    entrada = EntradaEcd(
        empresa=IdentificacaoEmpresaEcd(
            cnpj="12345678000190", razao_social="X LTDA",
            nome_fantasia=None, uf="SP", municipio=None,
            codigo_municipio_ibge="3550308",
        ),
        ano_calendario=2025,
        inicio_exercicio=date(2025, 1, 1),
        fim_exercicio=date(2025, 12, 31),
        plano_contas=plano,
        saldos_periodicos=(
            SaldoPeriodico(
                inicio=date(2025, 3, 1), fim=date(2025, 3, 31),
                saldos=(
                    SaldoPeriodicoConta(
                        codigo_conta="1.1.1.01",
                        saldo_inicial=Decimal("0"),
                        indicador_saldo_inicial="D",
                        total_debitos=Decimal("1000.00"),
                        total_creditos=Decimal("0"),
                        saldo_final=Decimal("1000.00"),
                        indicador_saldo_final="D",
                    ),
                ),
            ),
        ),
        lancamentos=(lanc,),
        saldos_resultado_antes_encerramento=(
            SaldoResultadoConta(
                codigo_conta="4.1.01", valor=Decimal("1000.00"),
                indicador_dc="C",
            ),
        ),
        balanco=(
            LinhaDemonstracao("1.01", 2, "D", "Ativo Circulante", Decimal("1000.00")),
            LinhaDemonstracao("1", 1, "D", "ATIVO TOTAL", Decimal("1000.00")),
        ),
        dre=(
            LinhaDemonstracao("3.01", 2, "C", "Receita Bruta", Decimal("1000.00")),
        ),
    )
    return gerar_ecd(entrada).conteudo.decode("latin-1")


def _ecf_perfeita() -> str:
    """ECF LP perfeita com 1 trimestre — gerador puro."""
    ap = ApuracaoTrimestralLp(
        inicio=date(2025, 1, 1),
        fim=date(2025, 3, 31),
        numero_trimestre=1,
        receita_bruta=Decimal("100000.00"),
        percentual_presuncao_irpj=Decimal("0.3200"),
        percentual_presuncao_csll=Decimal("0.3200"),
        base_presumida_irpj=Decimal("32000.00"),
        base_presumida_csll=Decimal("32000.00"),
        ganhos_capital=Decimal("0"),
        receitas_aplicacoes=Decimal("0"),
        outras_adicoes_irpj=Decimal("0"),
        outras_adicoes_csll=Decimal("0"),
        base_total_irpj=Decimal("32000.00"),
        base_total_csll=Decimal("32000.00"),
        limite_adicional_irpj=Decimal("60000.00"),
        irpj_normal=Decimal("4800.00"),
        irpj_adicional=Decimal("0"),
        irpj_total=Decimal("4800.00"),
        irrf_a_compensar=Decimal("0"),
        irrf_consumido=Decimal("0"),
        irpj_devido=Decimal("4800.00"),
        csll_devida=Decimal("2880.00"),
    )
    entrada = EntradaEcf(
        empresa=IdentificacaoEmpresaEcf(
            cnpj="12345678000190", razao_social="X LTDA",
            nome_fantasia=None, uf="SP", municipio=None,
            codigo_municipio_ibge="3550308",
        ),
        ano_calendario=2025,
        inicio_exercicio=date(2025, 1, 1),
        fim_exercicio=date(2025, 12, 31),
        forma_tributacao="4",
        ecd_vinculada=None,
        plano_contas=(
            ContaPlanoEcf(
                codigo="1.1.1.01", descricao="Caixa", natureza="D",
                nivel=4, tipo_conta="A", codigo_pai=None,
                codigo_ecd_referencial="1.01.01.01.01.01",
            ),
        ),
        saldos_por_trimestre=(
            (1, (
                SaldoContaTrimestre(
                    codigo_conta="1.1.1.01",
                    saldo_inicial=Decimal("0"),
                    indicador_saldo_inicial="D",
                    debitos=Decimal("100000.00"),
                    creditos=Decimal("0"),
                    saldo_final=Decimal("100000.00"),
                    indicador_saldo_final="D",
                ),
            )),
        ),
        apuracoes_trimestrais=(ap,),
        informacoes_gerais=InformacoesGerais(
            discriminacao_receita=(("01", Decimal("100000.00")),),
        ),
    )
    return gerar_ecf(entrada).conteudo.decode("latin-1")


# ── Validador estrutural ────────────────────────────────────────────────────


class TestEstruturaArquivoOk:
    def test_ecd_perfeita_passa_sem_erros(self) -> None:
        r = validar_ecd(_ecd_perfeita())
        assert r.ok
        assert r.total_erros == 0
        assert r.validador_versao == VALIDADOR_VERSAO

    def test_ecf_perfeita_passa_sem_erros(self) -> None:
        r = validar_ecf(_ecf_perfeita())
        assert r.ok
        assert r.total_erros == 0


class TestArquivoVazio:
    def test_arquivo_vazio_levanta_erro(self) -> None:
        r = validar_ecd("")
        assert not r.ok
        assert any(e.codigo == "estrutura.arquivo_vazio" for e in r.erros)


class TestLinhaQuebrada:
    def test_linha_sem_pipe_inicial_eh_erro(self) -> None:
        conteudo = _ecd_perfeita() + "linha sem pipe\n"
        r = validar_ecd(conteudo)
        assert any(e.codigo == "estrutura.linha_quebrada" for e in r.erros)


class Test9999:
    def test_9999_divergente_eh_erro(self) -> None:
        # Substitui o 9999 declarando 999.
        conteudo = _ecd_perfeita()
        linhas = conteudo.splitlines(keepends=True)
        linhas[-1] = "|9999|999|\n"
        r = validar_ecd("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "estrutura.9999_divergente" in codes


class Test9900:
    def test_9900_divergente_eh_erro(self) -> None:
        conteudo = _ecd_perfeita()
        # Achar a primeira linha 9900 e quebrar a contagem.
        linhas = conteudo.splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if ln.startswith("|9900|"):
                partes = ln.strip().split("|")
                # campos = ['', '9900', TIPO, QTD, '']
                partes[3] = "9999"
                linhas[i] = "|".join(partes) + "\n"
                break
        r = validar_ecd("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "estrutura.9900_divergente" in codes


class TestBlocoObrigatorio:
    def test_falta_bloco_j_eh_erro(self) -> None:
        # Remove a abertura J001 e o encerramento J990 do arquivo.
        conteudo = _ecd_perfeita()
        linhas = [
            ln for ln in conteudo.splitlines(keepends=True)
            if not (ln.startswith("|J001|") or ln.startswith("|J990|"))
        ]
        r = validar_ecd("".join(linhas))
        codes = {e.codigo for e in r.erros}
        # Pelo menos um dos dois é reportado (J001 e/ou J990 ausentes).
        assert (
            "estrutura.bloco_abertura_ausente" in codes
            or "estrutura.bloco_encerramento_ausente" in codes
        )


# ── Validador ECD — amarrações contábeis ────────────────────────────────────


class TestEcdAmarracoes:
    def test_partidas_desbalanceadas_eh_erro(self) -> None:
        """Quebra o crédito do I250 — soma D ≠ C."""
        conteudo = _ecd_perfeita()
        linhas = conteudo.splitlines(keepends=True)
        # Encontrar primeira I250 com IND_DC='C' e adulterar valor.
        for i, ln in enumerate(linhas):
            if ln.startswith("|I250|") and "|C|" in ln:
                # Layout I250: |I250|COD_CTA|COD_CCUS|VLR|IND_DC|HIST|HIST_PAD|
                partes = ln.strip().split("|")
                partes[4] = "999,00"  # crédito vira 999 ≠ 1000 débito
                linhas[i] = "|".join(partes) + "\n"
                break
        r = validar_ecd("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "ecd.partidas_desbalanceadas" in codes

    def test_conta_orfa_em_i155_eh_erro(self) -> None:
        """Insere um I155 referenciando código fora do I050."""
        linhas = _ecd_perfeita().splitlines(keepends=True)
        # Inserir um I155 após o primeiro I150.
        nova = "|I155|9.9.9.99||0,00|D|0,00|0,00|0,00|D|\n"
        for i, ln in enumerate(linhas):
            if ln.startswith("|I150|"):
                linhas.insert(i + 1, nova)
                break
        # Ajustar 9999 e 9900[I155] para passar pela estrutura (não é o foco
        # deste teste). Mais simples: deixar estrutura quebrar e só checar
        # que o erro semântico foi capturado.
        r = validar_ecd("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "ecd.i155_conta_orfa" in codes

    def test_indicador_invalido_em_i250(self) -> None:
        linhas = _ecd_perfeita().splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if ln.startswith("|I250|") and "|C|" in ln:
                partes = ln.strip().split("|")
                partes[5] = "X"  # IND_DC inválido
                linhas[i] = "|".join(partes) + "\n"
                break
        r = validar_ecd("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "ecd.i250_indicador_invalido" in codes


# ── Validador ECF — apuração LP ─────────────────────────────────────────────


class TestEcfApuracao:
    def test_p200_irpj_normal_divergente(self) -> None:
        """Quebra o irpj_normal — não bate com 15% × base."""
        linhas = _ecf_perfeita().splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if ln.startswith("|P200|"):
                # Layout: |P200|BASE|LIMITE|IRPJ_NORMAL|IRPJ_ADIC|IRPJ_TOTAL|IRRF|IRPJ_DEVIDO|
                partes = ln.strip().split("|")
                partes[4] = "9999,00"  # IRPJ normal completamente errado
                linhas[i] = "|".join(partes) + "\n"
                break
        r = validar_ecf("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "ecf.p200_irpj_normal_divergente" in codes

    def test_p200_total_divergente(self) -> None:
        """irpj_total ≠ irpj_normal + irpj_adicional."""
        linhas = _ecf_perfeita().splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if ln.startswith("|P200|"):
                partes = ln.strip().split("|")
                partes[6] = "9999,00"  # IRPJ total errado (normal=4800)
                linhas[i] = "|".join(partes) + "\n"
                break
        r = validar_ecf("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "ecf.p200_total_divergente" in codes

    def test_p300_csll_divergente(self) -> None:
        """csll declarada ≠ base × 9%."""
        linhas = _ecf_perfeita().splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if ln.startswith("|P300|"):
                # Layout: |P300|REC|PRES|BASE_PRES|OUTRAS|BASE_TOT|CSLL|
                partes = ln.strip().split("|")
                partes[7] = "9999,00"  # CSLL errada
                linhas[i] = "|".join(partes) + "\n"
                break
        r = validar_ecf("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "ecf.p300_csll_divergente" in codes

    def test_y540_diverge_de_p100(self) -> None:
        """Receita Y540 muito acima da soma trimestral P100."""
        linhas = _ecf_perfeita().splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if ln.startswith("|Y540|"):
                # Layout: |Y540|COD_ATIV|VALOR|
                partes = ln.strip().split("|")
                partes[3] = "999999,99"
                linhas[i] = "|".join(partes) + "\n"
                break
        r = validar_ecf("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "ecf.y540_p100_divergente" in codes


# ── Validador EFD-Contribuições (Sprint 17 PR1) ─────────────────────────────


def _efd_contribuicoes_perfeita() -> str:
    """Pequena EFD-Contribuições perfeita gerada pelo gerador puro."""
    entrada = EntradaEfdContribuicoes(
        empresa=IdentificacaoEmpresaEfd(
            cnpj="12345678000190",
            razao_social="X LTDA",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="3550308",
        ),
        competencia_inicio=date(2026, 3, 1),
        competencia_fim=date(2026, 3, 31),
        apuracao=ApuracaoMensalPisCofins(
            base_calculo_pis=Decimal("50000.00"),
            aliquota_pis=Decimal("0.65"),
            valor_pis_apurado=Decimal("325.00"),
            valor_pis_a_recolher=Decimal("325.00"),
            base_calculo_cofins=Decimal("50000.00"),
            aliquota_cofins=Decimal("3.00"),
            valor_cofins_apurado=Decimal("1500.00"),
            valor_cofins_a_recolher=Decimal("1500.00"),
        ),
        participantes=(
            ParticipanteEfd(
                codigo="99887766000155",
                nome="Cliente X",
                cnpj="99887766000155",
            ),
        ),
        mercadorias=(
            DocumentoMercadoriaEfd(
                chave="35260612345678000190550010000010011000000010",
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
                cfop="5102",
                ncm="22030000",
            ),
        ),
    )
    return gerar_efd_contribuicoes(entrada).conteudo.decode("latin-1")


class TestEfdContribuicoes:
    def test_arquivo_perfeito_passa_sem_erros(self) -> None:
        r = validar_efd_contribuicoes(_efd_contribuicoes_perfeita())
        assert r.ok, [e.codigo for e in r.erros]

    def test_falta_bloco_m_eh_erro(self) -> None:
        conteudo = _efd_contribuicoes_perfeita()
        linhas = [
            ln for ln in conteudo.splitlines(keepends=True)
            if not (ln.startswith("|M001|") or ln.startswith("|M990|"))
        ]
        r = validar_efd_contribuicoes("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "estrutura.bloco_abertura_ausente" in codes

    def test_pis_c170_com_valor_divergente_eh_erro(self) -> None:
        """Quebra deliberadamente o VL_PIS no C170 para o validador acusar.

        ``ln.split('|')`` produz ``['', 'C170', f0, f1, ..., '']`` — então
        o campo ``K`` do validador (índice em ``campos``) corresponde a
        ``partes[K + 2]``. VL_PIS é ``campos[28]`` → ``partes[30]``.
        """
        conteudo = _efd_contribuicoes_perfeita()
        linhas = conteudo.splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if not ln.startswith("|C170|"):
                continue
            partes = ln.strip().split("|")
            partes[30] = "99999,99"  # rebenta a coerência base × alíquota
            linhas[i] = "|".join(partes) + "\n"
            break
        r = validar_efd_contribuicoes("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "efd_contrib.c170_pis_divergente" in codes


# ── Validador EFD ICMS-IPI (Sprint 17 PR2) ──────────────────────────────────


def _efd_icms_ipi_perfeita() -> str:
    """EFD ICMS-IPI mínima gerada pelo gerador puro — comércio SP venda 18%."""
    entrada = EntradaEfdIcmsIpi(
        empresa=IdentificacaoEmpresaEfdIcms(
            cnpj="12345678000190",
            razao_social="Comércio SP LTDA",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="3550308",
            inscricao_estadual="111222333",
        ),
        competencia_inicio=date(2026, 3, 1),
        competencia_fim=date(2026, 3, 31),
        apuracao_icms=ApuracaoMensalIcms(
            valor_total_debitos=Decimal("9000.00"),
            valor_total_creditos=Decimal("0"),
            saldo_credor_anterior=Decimal("0"),
            ajustes_devedores=Decimal("0"),
            ajustes_credores=Decimal("0"),
            valor_icms_a_recolher=Decimal("9000.00"),
            saldo_credor_a_transportar=Decimal("0"),
        ),
        participantes=(
            ParticipanteIcms(
                codigo="99887766000155",
                nome="Cliente X",
                cnpj="99887766000155",
            ),
        ),
        documentos=(
            DocumentoIcmsEfd(
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
                cst_icms="000",
            ),
        ),
    )
    return gerar_efd_icms_ipi(entrada).conteudo.decode("latin-1")


class TestEfdIcmsIpi:
    def test_arquivo_perfeito_passa_sem_erros(self) -> None:
        r = validar_efd_icms_ipi(_efd_icms_ipi_perfeita())
        assert r.ok, [e.codigo for e in r.erros]

    def test_falta_bloco_e_eh_erro(self) -> None:
        conteudo = _efd_icms_ipi_perfeita()
        linhas = [
            ln for ln in conteudo.splitlines(keepends=True)
            if not (ln.startswith("|E001|") or ln.startswith("|E990|"))
        ]
        r = validar_efd_icms_ipi("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "estrutura.bloco_abertura_ausente" in codes

    def test_c170_com_icms_divergente_eh_erro(self) -> None:
        """Quebra VL_ICMS no C170 — campos no validador:
        ``campos[13]`` = VL_ICMS → ``partes[15]`` no split com pipes externos.
        """
        conteudo = _efd_icms_ipi_perfeita()
        linhas = conteudo.splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if not ln.startswith("|C170|"):
                continue
            partes = ln.strip().split("|")
            partes[15] = "99999,99"  # VL_ICMS
            linhas[i] = "|".join(partes) + "\n"
            break
        r = validar_efd_icms_ipi("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "efd_icms.c170_icms_divergente" in codes

    def test_e110_recolher_negativo_eh_erro(self) -> None:
        """VL_ICMS_RECOLHER = campos[11] do validador → partes[13] no split."""
        conteudo = _efd_icms_ipi_perfeita()
        linhas = conteudo.splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if not ln.startswith("|E110|"):
                continue
            partes = ln.strip().split("|")
            partes[13] = "-100,00"  # VL_ICMS_RECOLHER
            linhas[i] = "|".join(partes) + "\n"
            break
        r = validar_efd_icms_ipi("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "efd_icms.e110_recolher_negativo" in codes


# ── Anti-regressão FIX #1 — validador detecta 9990 off-by-one ───────────────


class TestValidador9990OffByOne:
    """Anti-regressão do bug #1 (auditoria 2026-06-04).

    O validador agora verifica o 9990 além do 9999. Um arquivo com o 9990
    calculado com a fórmula antiga (+1 em vez de +2) deve ser rejeitado.

    Antes da correção do validador, esses arquivos passavam aqui mas eram
    rejeitados pelo PVA — a barreira de defesa estava ausente.
    """

    def test_9990_divergente_eh_erro(self) -> None:
        """Altera o 9990 para um valor incorreto e verifica que é rejeitado."""
        conteudo = _efd_contribuicoes_perfeita()
        linhas = conteudo.splitlines(keepends=True)
        for i, ln in enumerate(linhas):
            if ln.startswith("|9990|"):
                partes = ln.strip().split("|")
                qtd_real = int(partes[2])
                partes[2] = str(qtd_real - 1)  # simula o off-by-one antigo
                linhas[i] = "|".join(partes) + "\n"
                break
        r = validar_efd_contribuicoes("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "estrutura.9990_divergente" in codes, (
            f"Esperado 'estrutura.9990_divergente' nos erros, mas got: {codes}"
        )

    def test_arquivo_gerado_pelo_gerador_passa_validacao_9990(self) -> None:
        """O gerador corrigido produz 9990 correto — validador aceita."""
        r = validar_efd_contribuicoes(_efd_contribuicoes_perfeita())
        # Não deve haver erro de 9990.
        codes = {e.codigo for e in r.erros}
        assert "estrutura.9990_divergente" not in codes, (
            f"Arquivo gerado tem 9990 incorreto: {codes}"
        )
        assert "estrutura.9990_ausente" not in codes

    def test_9990_ausente_eh_erro(self) -> None:
        """Remove o 9990 e verifica que o validador acusa ausência."""
        conteudo = _efd_contribuicoes_perfeita()
        linhas = [
            ln for ln in conteudo.splitlines(keepends=True)
            if not ln.startswith("|9990|")
        ]
        r = validar_efd_contribuicoes("".join(linhas))
        codes = {e.codigo for e in r.erros}
        assert "estrutura.9990_ausente" in codes


# ── Dispatcher + serialização JSONB ─────────────────────────────────────────


class TestDispatcher:
    def test_tipo_ecd_chama_validar_ecd(self) -> None:
        r = validar_por_tipo("ecd", _ecd_perfeita())
        assert r.ok

    def test_tipo_ecf_chama_validar_ecf(self) -> None:
        r = validar_por_tipo("ecf", _ecf_perfeita())
        assert r.ok

    def test_tipo_efd_contribuicoes_chama_validar_efd_contribuicoes(self) -> None:
        r = validar_por_tipo("efd_contribuicoes", _efd_contribuicoes_perfeita())
        assert r.ok

    def test_tipo_efd_icms_ipi_chama_validar_efd_icms_ipi(self) -> None:
        r = validar_por_tipo("efd_icms_ipi", _efd_icms_ipi_perfeita())
        assert r.ok

    def test_tipo_desconhecido_devolve_erro(self) -> None:
        r = validar_por_tipo("tipo_inexistente", _ecd_perfeita())
        codes = {e.codigo for e in r.erros}
        assert "validador.tipo_nao_suportado" in codes


class TestSerializacaoJsonb:
    def test_resultado_para_jsonb_estrutura(self) -> None:
        r = validar_ecd(_ecd_perfeita())
        j = resultado_para_jsonb(r)
        assert j["ok"] is True
        assert j["total_erros"] == 0
        assert j["total_warnings"] == 0
        assert j["validador_versao"] == VALIDADOR_VERSAO
        assert j["erros"] == []
        assert j["warnings"] == []

    def test_resultado_para_jsonb_com_erros(self) -> None:
        r = validar_ecd("")
        j = resultado_para_jsonb(r)
        assert j["ok"] is False
        assert j["total_erros"] >= 1
        assert isinstance(j["erros"], list)
        assert j["erros"][0]["codigo"] == "estrutura.arquivo_vazio"
        assert "severidade" in j["erros"][0]
        assert "contexto" in j["erros"][0]
