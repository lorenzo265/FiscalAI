"""Testes do serializador comum SPED (Sprint 16 PR1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.sped.compartilhado import (
    calcular_hash_sha256,
    contar_registros,
    escapar,
    formatar_data,
    formatar_decimal,
    formatar_periodo,
    gerar_bloco_9,
    linha,
    montar_arquivo,
)


class TestEscapar:
    def test_substitui_pipe_por_hifen(self) -> None:
        assert escapar("foo|bar|baz") == "foo-bar-baz"

    def test_substitui_cr_lf_por_espaco(self) -> None:
        assert escapar("linha 1\nlinha 2") == "linha 1 linha 2"
        assert escapar("linha\rback") == "linha back"

    def test_string_limpa_passa(self) -> None:
        assert escapar("Histórico contábil padrão") == "Histórico contábil padrão"

    def test_string_vazia_continua_vazia(self) -> None:
        assert escapar("") == ""


class TestFormatarDecimal:
    def test_zero(self) -> None:
        assert formatar_decimal(Decimal("0")) == "0,00"

    def test_inteiro(self) -> None:
        assert formatar_decimal(Decimal("100")) == "100,00"

    def test_centavos(self) -> None:
        assert formatar_decimal(Decimal("1234.56")) == "1234,56"

    def test_negativo_preserva_sinal(self) -> None:
        assert formatar_decimal(Decimal("-12.34")) == "-12,34"

    def test_quantize_half_even(self) -> None:
        # 0.125 → 0.12 (banker's: par)
        assert formatar_decimal(Decimal("0.125")) == "0,12"
        # 0.135 → 0.14 (banker's: par)
        assert formatar_decimal(Decimal("0.135")) == "0,14"

    def test_sem_separador_de_milhar(self) -> None:
        assert formatar_decimal(Decimal("1234567.89")) == "1234567,89"

    def test_aceita_int_e_float(self) -> None:
        assert formatar_decimal(100) == "100,00"
        assert formatar_decimal(1.5) == "1,50"


class TestFormatarData:
    def test_padrao_ddmmaaaa(self) -> None:
        assert formatar_data(date(2025, 12, 31)) == "31122025"

    def test_dia_unitario_zero_padded(self) -> None:
        assert formatar_data(date(2026, 1, 5)) == "05012026"


class TestFormatarPeriodo:
    def test_padrao_mmaaaa(self) -> None:
        assert formatar_periodo(date(2025, 12, 1)) == "122025"

    def test_mes_unitario_zero_padded(self) -> None:
        assert formatar_periodo(date(2026, 3, 1)) == "032026"


class TestLinha:
    def test_estrutura_pipe_inicio_fim_e_lf(self) -> None:
        ln = linha("0000", "10.00", "0")
        assert ln.startswith("|")
        assert ln.endswith("|\n")

    def test_campos_vazios_preservam_pipes(self) -> None:
        ln = linha("0000", "v1", None, "v3")
        assert ln == "|0000|v1||v3|\n"

    def test_none_vira_vazio(self) -> None:
        ln = linha("X", None, None)
        assert ln == "|X|||\n"

    def test_decimal_formatado(self) -> None:
        ln = linha("I250", Decimal("1234.56"))
        assert ln == "|I250|1234,56|\n"

    def test_date_formatado_ddmmaaaa(self) -> None:
        ln = linha("0000", date(2025, 1, 1))
        assert ln == "|0000|01012025|\n"

    def test_bool_sn(self) -> None:
        assert linha("X", True) == "|X|S|\n"
        assert linha("X", False) == "|X|N|\n"

    def test_pipe_no_texto_e_escapado(self) -> None:
        ln = linha("I250", "histórico|com|pipe")
        assert ln == "|I250|histórico-com-pipe|\n"


class TestContarRegistros:
    def test_conta_por_tipo(self) -> None:
        linhas = [
            linha("0000", "10"),
            linha("0001", "0"),
            linha("0030", "1"),
            linha("0030", "2"),
            linha("0990", "4"),
        ]
        c = contar_registros(linhas)
        assert c == {"0000": 1, "0001": 1, "0030": 2, "0990": 1}

    def test_ignora_linhas_vazias(self) -> None:
        c = contar_registros(["", "\n", "|0000|x|\n"])
        assert c == {"0000": 1}

    def test_ignora_linhas_sem_pipe_inicial(self) -> None:
        c = contar_registros(["sem pipe\n", "|0001|0|\n"])
        assert c == {"0001": 1}


class TestGerarBloco9:
    def test_totaliza_corretamente_arquivo_minimo(self) -> None:
        # 3 registros simples no bloco 0.
        anteriores = [
            linha("0000", "10"),
            linha("0001", "0"),
            linha("0990", "2"),
        ]
        bloco_9 = gerar_bloco_9(anteriores)
        tipos_9 = [ln.split("|")[1] for ln in bloco_9]
        # Tem que aparecer 9001, várias 9900, 9990, 9999.
        assert tipos_9[0] == "9001"
        assert "9990" in tipos_9
        assert tipos_9[-1] == "9999"

    def test_total_geral_9999_bate_com_arquivo_completo(self) -> None:
        anteriores = [
            linha("0000", "10"),
            linha("0001", "0"),
            linha("0030", "1"),
            linha("0990", "3"),
        ]
        bloco_9 = gerar_bloco_9(anteriores)
        # 9999 está na última linha; total geral = anteriores + bloco_9.
        total_geral = int(bloco_9[-1].split("|")[2])
        assert total_geral == len(anteriores) + len(bloco_9)

    def test_9900_aparece_para_si_mesmo_e_pra_9999(self) -> None:
        anteriores = [linha("0000", "10")]
        bloco_9 = gerar_bloco_9(anteriores)
        # Pelo menos uma 9900 vai contar a si mesma e outra vai contar o 9999.
        regs_em_9900 = [
            ln.split("|")[2] for ln in bloco_9 if ln.startswith("|9900|")
        ]
        assert "9900" in regs_em_9900
        assert "9999" in regs_em_9900
        assert "9990" in regs_em_9900

    def test_contagem_de_cada_9900_consistente(self) -> None:
        """Verifica que cada 9900 conta corretamente seu tipo no arquivo final.

        O arquivo completo = ``anteriores`` + ``bloco_9``. Para cada tipo,
        contagem real == número declarado no 9900 correspondente.
        """
        anteriores = [
            linha("0000", "10"),
            linha("0001", "0"),
            linha("I050", "01012025", "01", "A", "1", "D", "1.1.1.01", "1.1.1", "Caixa"),
            linha("I050", "01012025", "01", "A", "1", "D", "1.1.1.02", "1.1.1", "Bancos"),
            linha("0990", "3"),
        ]
        bloco_9 = gerar_bloco_9(anteriores)
        arquivo_completo = anteriores + bloco_9
        contagem_real = contar_registros(arquivo_completo)

        # Para cada linha 9900 do bloco, verificar tipo e quantidade.
        for ln in bloco_9:
            if not ln.startswith("|9900|"):
                continue
            campos = ln.split("|")
            tipo_declarado = campos[2]
            qtd_declarada = int(campos[3])
            assert contagem_real.get(tipo_declarado) == qtd_declarada, (
                f"Tipo {tipo_declarado}: contagem real "
                f"{contagem_real.get(tipo_declarado)} != declarada "
                f"{qtd_declarada}"
            )


    def test_9990_conta_ele_proprio_e_9999_anti_regressao(self) -> None:
        """Anti-regressão do bug #1 (auditoria 2026-06-04).

        O bloco 9 é composto por: 9001 (1) + 9900 × N + 9990 (1) + 9999 (1).
        O registro 9990 deve declarar a contagem de TODAS essas linhas,
        incluindo o próprio 9999.  O bug anterior contava +1 (esquecia o 9999),
        o que fazia o PVA rejeitar todos os arquivos.

        Este teste falha com a implementação anterior (``total_bloco_9 = ... + 1``).
        """
        anteriores = [
            linha("0000", "10"),
            linha("0001", "0"),
            linha("0990", "2"),
        ]
        bloco_9 = gerar_bloco_9(anteriores)

        # Localiza o 9990 e lê o valor declarado.
        qtd_9990_declarada = -1
        for ln in bloco_9:
            if ln.startswith("|9990|"):
                qtd_9990_declarada = int(ln.split("|")[2])
                break
        assert qtd_9990_declarada >= 0, "9990 não encontrado no bloco 9"

        # Conta as linhas do bloco 9 efetivamente emitidas (9001+9900*N+9990+9999).
        qtd_bloco_9_real = sum(
            1 for ln in bloco_9
            if ln.startswith("|9001|")
            or ln.startswith("|9900|")
            or ln.startswith("|9990|")
            or ln.startswith("|9999|")
        )
        assert qtd_9990_declarada == qtd_bloco_9_real, (
            f"9990 declara {qtd_9990_declarada} mas bloco 9 tem "
            f"{qtd_bloco_9_real} linhas — off-by-one detectado."
        )

    def test_9990_inclui_9999_no_total_bloco_9(self) -> None:
        """Verifica explicitamente que 9999 é contabilizado no QTD_LIN_9.

        Com o bug anterior, o 9990 declarava (N+2) quando o bloco tinha
        (N+3) linhas reais — o 9999 não era somado.
        """
        anteriores = [linha("0000", "v")]
        bloco_9 = gerar_bloco_9(anteriores)

        # Contagem real dos registros do bloco 9.
        regs_bloco_9 = {"9001", "9900", "9990", "9999"}
        n_real = sum(
            1 for ln in bloco_9
            if ln.split("|")[1] in regs_bloco_9
        )

        # Valor declarado pelo 9990.
        linha_9990 = next(ln for ln in bloco_9 if ln.startswith("|9990|"))
        n_declarado = int(linha_9990.split("|")[2])

        assert n_declarado == n_real
        # E 9999 está incluído nessa conta (não é n_real - 1 como no bug).
        n_sem_9999 = sum(
            1 for ln in bloco_9
            if ln.split("|")[1] in {"9001", "9900", "9990"}
        )
        assert n_declarado > n_sem_9999, (
            "9990 não inclui 9999 no total do bloco — off-by-one!"
        )


class TestCalcularHashSha256:
    def test_hash_estavel(self) -> None:
        h1 = calcular_hash_sha256(b"|0000|10|\n")
        h2 = calcular_hash_sha256(b"|0000|10|\n")
        assert h1 == h2

    def test_hash_64_chars_hex(self) -> None:
        h = calcular_hash_sha256(b"x")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_muda_com_qualquer_byte(self) -> None:
        h1 = calcular_hash_sha256(b"abc")
        h2 = calcular_hash_sha256(b"abd")
        assert h1 != h2


class TestMontarArquivo:
    def test_concatena_e_codifica_latin1(self) -> None:
        linhas = ["|0000|teste|\n", "|0001|0|\n"]
        bytes_arq = montar_arquivo(linhas)
        assert bytes_arq == b"|0000|teste|\n|0001|0|\n"

    def test_acento_latin_codifica(self) -> None:
        linhas = [linha("0030", "Histórico São Paulo")]
        bytes_arq = montar_arquivo(linhas)
        # Em latin-1 acentos codificam em 1 byte.
        assert bytes_arq.decode("latin-1") == "|0030|Histórico São Paulo|\n"

    def test_caractere_fora_latin1_vira_interrogacao(self) -> None:
        # Caractere chinês não cabe em latin-1.
        bytes_arq = montar_arquivo(["|X|中文|\n"])
        # Substituído por ?
        assert bytes_arq == b"|X|??|\n"
