"""Testes do gerador ECF Lucro Presumido (Sprint 16 PR2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.sped.compartilhado import contar_registros
from app.modules.sped.ecf.gerador import (
    ALGORITMO_VERSAO,
    ApuracaoTrimestralLp,
    ContaPlanoEcf,
    EcdVinculada,
    EntradaEcf,
    IdentificacaoEmpresaEcf,
    InformacoesGerais,
    SaldoContaTrimestre,
    _EntradaEcfInvalida,
    gerar_ecf,
)


def _empresa() -> IdentificacaoEmpresaEcf:
    return IdentificacaoEmpresaEcf(
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


def _plano() -> tuple[ContaPlanoEcf, ...]:
    return (
        ContaPlanoEcf(
            codigo="1", descricao="ATIVO", natureza="D", nivel=1,
            tipo_conta="S", codigo_pai=None,
            codigo_ecd_referencial="1",
        ),
        ContaPlanoEcf(
            codigo="1.1.1.01", descricao="Caixa", natureza="D", nivel=4,
            tipo_conta="A", codigo_pai="1",
            codigo_ecd_referencial="1.01.01.01.01.01",
        ),
        ContaPlanoEcf(
            codigo="4.1.01", descricao="Receita Serviços", natureza="C", nivel=3,
            tipo_conta="A", codigo_pai=None,
            codigo_ecd_referencial="4.01.01.01.01.01",
        ),
    )


def _apuracao(numero: int) -> ApuracaoTrimestralLp:
    """Trimestre típico LP serviços (32% IRPJ, 32% CSLL) — R$ 100k receita."""
    inicio = date(2025, 3 * (numero - 1) + 1, 1)
    mes_fim = 3 * (numero - 1) + 3
    from datetime import timedelta
    fim = date(2025, 12, 31) if mes_fim == 12 else date(2025, mes_fim + 1, 1) - timedelta(days=1)
    receita = Decimal("100000.00")
    pres_irpj = Decimal("0.3200")
    pres_csll = Decimal("0.3200")
    base_irpj = receita * pres_irpj  # 32000
    base_csll = receita * pres_csll
    irpj_normal = base_irpj * Decimal("0.15")  # 4800
    # Sem adicional (32k < 60k = 3 meses × 20k)
    return ApuracaoTrimestralLp(
        inicio=inicio,
        fim=fim,
        numero_trimestre=numero,
        receita_bruta=receita,
        percentual_presuncao_irpj=pres_irpj,
        percentual_presuncao_csll=pres_csll,
        base_presumida_irpj=base_irpj,
        base_presumida_csll=base_csll,
        ganhos_capital=Decimal("0"),
        receitas_aplicacoes=Decimal("0"),
        outras_adicoes_irpj=Decimal("0"),
        outras_adicoes_csll=Decimal("0"),
        base_total_irpj=base_irpj,
        base_total_csll=base_csll,
        limite_adicional_irpj=Decimal("60000.00"),
        irpj_normal=irpj_normal,
        irpj_adicional=Decimal("0"),
        irpj_total=irpj_normal,
        irrf_a_compensar=Decimal("0"),
        irrf_consumido=Decimal("0"),
        irpj_devido=irpj_normal,
        csll_devida=base_csll * Decimal("0.09"),  # 2880
    )


def _entrada_minima(
    *, com_ecd: bool = False, num_trimestres: int = 4,
) -> EntradaEcf:
    ecd = None
    if com_ecd:
        ecd = EcdVinculada(
            hash_ecd="a" * 64,
            num_recibo_ecd="RECECD123",
            data_recibo=date(2026, 5, 30),
        )
    return EntradaEcf(
        empresa=_empresa(),
        ano_calendario=2025,
        inicio_exercicio=date(2025, 1, 1),
        fim_exercicio=date(2025, 12, 31),
        forma_tributacao="4",  # LP
        ecd_vinculada=ecd,
        plano_contas=_plano(),
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
        apuracoes_trimestrais=tuple(
            _apuracao(n) for n in range(1, num_trimestres + 1)
        ),
        informacoes_gerais=InformacoesGerais(
            discriminacao_receita=(("01", Decimal("400000.00")),),
            socios=(),
        ),
    )


# ── Happy path ─────────────────────────────────────────────────────────────


class TestGerarEcfHappyPath:
    def test_retorna_bytes_e_hash(self) -> None:
        out = gerar_ecf(_entrada_minima())
        assert isinstance(out.conteudo, bytes)
        assert len(out.hash_sha256) == 64
        assert out.tamanho_bytes == len(out.conteudo)
        assert out.algoritmo_versao == ALGORITMO_VERSAO

    def test_arquivo_comeca_com_0000(self) -> None:
        out = gerar_ecf(_entrada_minima())
        assert out.conteudo.decode("latin-1").startswith("|0000|LECF|")

    def test_arquivo_termina_com_9999(self) -> None:
        out = gerar_ecf(_entrada_minima())
        ultima = out.conteudo.decode("latin-1").splitlines()[-1]
        assert ultima.startswith("|9999|")

    def test_9999_bate_com_total_de_linhas(self) -> None:
        out = gerar_ecf(_entrada_minima())
        linhas = out.conteudo.decode("latin-1").splitlines()
        total = int(linhas[-1].split("|")[2])
        assert total == len(linhas) == out.total_linhas

    def test_hash_estavel(self) -> None:
        e = _entrada_minima()
        assert gerar_ecf(e).hash_sha256 == gerar_ecf(e).hash_sha256


# ── Blocos obrigatórios + LP-específico ───────────────────────────────────


class TestBlocosObrigatorios:
    def test_todos_blocos_tem_abertura_e_encerramento(self) -> None:
        out = gerar_ecf(_entrada_minima())
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        # Todos os blocos do ECF v10 precisam estar presentes.
        for bloco in ("0", "C", "E", "J", "K", "L", "M", "N", "P", "Q",
                      "T", "U", "V", "W", "X", "Y", "9"):
            assert regs.get(f"{bloco}001", 0) == 1, f"Bloco {bloco}001 ausente"
            assert regs.get(f"{bloco}990", 0) == 1, f"Bloco {bloco}990 ausente"
        assert regs["9999"] == 1

    def test_p010_uma_linha_por_trimestre(self) -> None:
        out = gerar_ecf(_entrada_minima())
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        assert regs["P010"] == 4

    def test_p200_e_p300_uma_linha_por_trimestre(self) -> None:
        out = gerar_ecf(_entrada_minima())
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        assert regs["P200"] == 4
        assert regs["P300"] == 4

    def test_p200_tem_irpj_correto_no_campo(self) -> None:
        """Verifica que P200 carrega o IRPJ total e devido corretos."""
        out = gerar_ecf(_entrada_minima())
        linhas = out.conteudo.decode("latin-1").splitlines()
        p200 = [ln for ln in linhas if ln.startswith("|P200|")]
        # Layout: |P200|BASE_IRPJ|LIMITE_ADIC|IRPJ_NORMAL|IRPJ_ADIC|IRPJ_TOTAL|IRRF_CONS|IRPJ_DEVIDO|
        primeiro = p200[0].split("|")
        assert primeiro[2] == "32000,00"  # base
        assert primeiro[3] == "60000,00"  # limite
        assert primeiro[4] == "4800,00"   # IRPJ normal
        assert primeiro[5] == "0,00"      # IRPJ adicional
        assert primeiro[6] == "4800,00"   # IRPJ total
        assert primeiro[7] == "0,00"      # IRRF consumido
        assert primeiro[8] == "4800,00"   # IRPJ devido

    def test_p300_tem_csll_correto(self) -> None:
        out = gerar_ecf(_entrada_minima())
        linhas = out.conteudo.decode("latin-1").splitlines()
        p300 = [ln for ln in linhas if ln.startswith("|P300|")]
        # Layout: |P300|REC|PRES|BASE_PRES|OUTRAS_AD|BASE_TOT|CSLL|
        primeiro = p300[0].split("|")
        assert primeiro[2] == "100000,00"  # receita
        assert primeiro[3] == "0,32"       # presunção (2 casas decimais)
        assert primeiro[4] == "32000,00"   # base presumida
        assert primeiro[6] == "32000,00"   # base total
        assert primeiro[7] == "2880,00"    # CSLL (9% × 32000)

    def test_bloco_n_vazio_em_lp(self) -> None:
        out = gerar_ecf(_entrada_minima())
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        # N tem só abertura + encerramento = 2 registros.
        assert regs["N001"] == 1
        assert regs["N990"] == 1
        # Conteúdo de Lucro Real (N030, N500, N620, etc.) não aparece.
        assert "N030" not in regs
        assert "N500" not in regs


class TestEcdVinculada:
    def test_c040_aparece_quando_ecd_existe(self) -> None:
        out = gerar_ecf(_entrada_minima(com_ecd=True))
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        assert regs["C040"] == 1

    def test_c040_ausente_quando_sem_ecd(self) -> None:
        out = gerar_ecf(_entrada_minima(com_ecd=False))
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        assert "C040" not in regs

    def test_c001_ind_dad_zero_quando_tem_ecd(self) -> None:
        out = gerar_ecf(_entrada_minima(com_ecd=True))
        linhas = out.conteudo.decode("latin-1").splitlines()
        c001 = next(ln for ln in linhas if ln.startswith("|C001|"))
        assert c001.split("|")[2] == "0"

    def test_c001_ind_dad_um_quando_sem_ecd(self) -> None:
        out = gerar_ecf(_entrada_minima(com_ecd=False))
        linhas = out.conteudo.decode("latin-1").splitlines()
        c001 = next(ln for ln in linhas if ln.startswith("|C001|"))
        assert c001.split("|")[2] == "1"


class TestK155SaldosTrimestre:
    def test_k155_uma_linha_por_conta_com_saldo(self) -> None:
        out = gerar_ecf(_entrada_minima())
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        # 1 trimestre com 1 conta na fixture.
        assert regs["K155"] == 1
        assert regs["K030"] == 1


class TestY540:
    def test_y540_emitido_com_receita_anual(self) -> None:
        out = gerar_ecf(_entrada_minima())
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        assert regs["Y540"] == 1

    def test_y540_omitido_se_sem_receita(self) -> None:
        e = _entrada_minima()
        sem_info = EntradaEcf(
            empresa=e.empresa,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            forma_tributacao=e.forma_tributacao,
            ecd_vinculada=e.ecd_vinculada,
            plano_contas=e.plano_contas,
            saldos_por_trimestre=e.saldos_por_trimestre,
            apuracoes_trimestrais=e.apuracoes_trimestrais,
            informacoes_gerais=InformacoesGerais(),
        )
        out = gerar_ecf(sem_info)
        regs = contar_registros(
            out.conteudo.decode("latin-1").splitlines(keepends=True)
        )
        assert "Y540" not in regs


# ── Validações de pré-condição ─────────────────────────────────────────────


class TestValidacoes:
    def test_cnpj_invalido_levanta(self) -> None:
        e = _entrada_minima()
        empresa_ruim = IdentificacaoEmpresaEcf(
            cnpj="123",
            razao_social="X",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="3550308",
        )
        entrada = EntradaEcf(
            empresa=empresa_ruim,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            forma_tributacao=e.forma_tributacao,
            ecd_vinculada=e.ecd_vinculada,
            plano_contas=e.plano_contas,
            saldos_por_trimestre=e.saldos_por_trimestre,
            apuracoes_trimestrais=e.apuracoes_trimestrais,
            informacoes_gerais=e.informacoes_gerais,
        )
        with pytest.raises(_EntradaEcfInvalida, match="CNPJ"):
            gerar_ecf(entrada)

    def test_forma_tributacao_invalida_levanta(self) -> None:
        e = _entrada_minima()
        entrada = EntradaEcf(
            empresa=e.empresa,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            forma_tributacao="X",  # ← inválido
            ecd_vinculada=e.ecd_vinculada,
            plano_contas=e.plano_contas,
            saldos_por_trimestre=e.saldos_por_trimestre,
            apuracoes_trimestrais=e.apuracoes_trimestrais,
            informacoes_gerais=e.informacoes_gerais,
        )
        with pytest.raises(_EntradaEcfInvalida, match="forma_tributacao"):
            gerar_ecf(entrada)

    def test_trimestre_duplicado_levanta(self) -> None:
        e = _entrada_minima(num_trimestres=2)
        # Cria duplicata propositalmente.
        duplicada = ApuracaoTrimestralLp(
            inicio=date(2025, 1, 1),
            fim=date(2025, 3, 31),
            numero_trimestre=1,  # ← já existe
            receita_bruta=Decimal("0"),
            percentual_presuncao_irpj=Decimal("0"),
            percentual_presuncao_csll=Decimal("0"),
            base_presumida_irpj=Decimal("0"),
            base_presumida_csll=Decimal("0"),
            ganhos_capital=Decimal("0"),
            receitas_aplicacoes=Decimal("0"),
            outras_adicoes_irpj=Decimal("0"),
            outras_adicoes_csll=Decimal("0"),
            base_total_irpj=Decimal("0"),
            base_total_csll=Decimal("0"),
            limite_adicional_irpj=Decimal("60000.00"),
            irpj_normal=Decimal("0"),
            irpj_adicional=Decimal("0"),
            irpj_total=Decimal("0"),
            irrf_a_compensar=Decimal("0"),
            irrf_consumido=Decimal("0"),
            irpj_devido=Decimal("0"),
            csll_devida=Decimal("0"),
        )
        entrada = EntradaEcf(
            empresa=e.empresa,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            forma_tributacao=e.forma_tributacao,
            ecd_vinculada=e.ecd_vinculada,
            plano_contas=e.plano_contas,
            saldos_por_trimestre=e.saldos_por_trimestre,
            apuracoes_trimestrais=(*e.apuracoes_trimestrais, duplicada),
            informacoes_gerais=e.informacoes_gerais,
        )
        with pytest.raises(_EntradaEcfInvalida, match="duplicado"):
            gerar_ecf(entrada)

    def test_saldo_em_conta_fora_do_plano_levanta(self) -> None:
        e = _entrada_minima()
        bad_saldos = (
            (1, (SaldoContaTrimestre(
                codigo_conta="9.9.9.99",  # ← inexistente
                saldo_inicial=Decimal("0"),
                indicador_saldo_inicial="D",
                debitos=Decimal("0"),
                creditos=Decimal("0"),
                saldo_final=Decimal("0"),
                indicador_saldo_final="D",
            ),)),
        )
        entrada = EntradaEcf(
            empresa=e.empresa,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            forma_tributacao=e.forma_tributacao,
            ecd_vinculada=e.ecd_vinculada,
            plano_contas=e.plano_contas,
            saldos_por_trimestre=bad_saldos,
            apuracoes_trimestrais=e.apuracoes_trimestrais,
            informacoes_gerais=e.informacoes_gerais,
        )
        with pytest.raises(_EntradaEcfInvalida, match="ausente do plano"):
            gerar_ecf(entrada)


# ── Consistência 9900 ─────────────────────────────────────────────────────


class TestConsistencia9900:
    def test_cada_9900_consistente_com_arquivo_completo(self) -> None:
        out = gerar_ecf(_entrada_minima())
        linhas = out.conteudo.decode("latin-1").splitlines(keepends=True)
        contagem_real = contar_registros(linhas)
        for ln in linhas:
            if not ln.startswith("|9900|"):
                continue
            campos = ln.strip().split("|")
            tipo, qtd = campos[2], int(campos[3])
            assert contagem_real.get(tipo) == qtd, (
                f"9900 declara {tipo}={qtd} mas há {contagem_real.get(tipo)}"
            )
