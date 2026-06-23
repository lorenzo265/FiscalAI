"""Testes do gerador ECD (Sprint 16 PR1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.sped.compartilhado import contar_registros
from app.modules.sped.ecd.gerador import (
    ALGORITMO_VERSAO,
    ContaPlano,
    EntradaEcd,
    IdentificacaoEmpresaEcd,
    LancamentoEcd,
    LinhaDemonstracao,
    PartidaLanc,
    SaldoPeriodico,
    SaldoPeriodicoConta,
    SaldoResultadoConta,
    _EntradaEcdInvalida,
    gerar_ecd,
)

# ── Fixtures de input mínimo ──────────────────────────────────────────────


def _empresa() -> IdentificacaoEmpresaEcd:
    return IdentificacaoEmpresaEcd(
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


def _plano_minimo() -> tuple[ContaPlano, ...]:
    """Plano de contas mínimo: caixa + receita serviços + CMV."""
    return (
        ContaPlano(
            codigo="1", descricao="ATIVO", natureza="D", nivel=1,
            tipo_conta="S", codigo_pai=None,
            codigo_ecd_referencial="1",
        ),
        ContaPlano(
            codigo="1.1", descricao="ATIVO CIRCULANTE", natureza="D", nivel=2,
            tipo_conta="S", codigo_pai="1",
            codigo_ecd_referencial="1.01",
        ),
        ContaPlano(
            codigo="1.1.1.01", descricao="Caixa", natureza="D", nivel=4,
            tipo_conta="A", codigo_pai="1.1",
            codigo_ecd_referencial="1.01.01.01.01.01",
        ),
        ContaPlano(
            codigo="4", descricao="RECEITAS", natureza="C", nivel=1,
            tipo_conta="S", codigo_pai=None,
            codigo_ecd_referencial="4",
        ),
        ContaPlano(
            codigo="4.1.01", descricao="Receita de Serviços", natureza="C",
            nivel=3, tipo_conta="A", codigo_pai="4",
            codigo_ecd_referencial="4.01.01.01.01.01",
        ),
        ContaPlano(
            codigo="5", descricao="DESPESAS", natureza="D", nivel=1,
            tipo_conta="S", codigo_pai=None,
            codigo_ecd_referencial="4.99",
        ),
        ContaPlano(
            codigo="5.1.01", descricao="CMV", natureza="D", nivel=3,
            tipo_conta="A", codigo_pai="5",
            codigo_ecd_referencial="4.02.01.01.01.01",
        ),
    )


def _lancamento_balanceado() -> LancamentoEcd:
    """Recebimento de R$ 1.000 em caixa por receita de serviço."""
    return LancamentoEcd(
        numero="1",
        data=date(2025, 3, 15),
        valor_total=Decimal("1000.00"),
        indicador_origem="N",
        partidas=(
            PartidaLanc(
                codigo_conta="1.1.1.01",
                valor=Decimal("1000.00"),
                indicador_dc="D",
                historico="Recebimento serviço prestado",
            ),
            PartidaLanc(
                codigo_conta="4.1.01",
                valor=Decimal("1000.00"),
                indicador_dc="C",
                historico="Recebimento serviço prestado",
            ),
        ),
    )


def _entrada_minima(
    *, lancamentos: tuple[LancamentoEcd, ...] | None = None,
) -> EntradaEcd:
    if lancamentos is None:
        lancamentos = (_lancamento_balanceado(),)
    return EntradaEcd(
        empresa=_empresa(),
        ano_calendario=2025,
        inicio_exercicio=date(2025, 1, 1),
        fim_exercicio=date(2025, 12, 31),
        plano_contas=_plano_minimo(),
        saldos_periodicos=(
            SaldoPeriodico(
                inicio=date(2025, 3, 1),
                fim=date(2025, 3, 31),
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
                    SaldoPeriodicoConta(
                        codigo_conta="4.1.01",
                        saldo_inicial=Decimal("0"),
                        indicador_saldo_inicial="C",
                        total_debitos=Decimal("0"),
                        total_creditos=Decimal("1000.00"),
                        saldo_final=Decimal("1000.00"),
                        indicador_saldo_final="C",
                    ),
                ),
            ),
        ),
        lancamentos=lancamentos,
        saldos_resultado_antes_encerramento=(
            SaldoResultadoConta(
                codigo_conta="4.1.01",
                valor=Decimal("1000.00"),
                indicador_dc="C",
            ),
            SaldoResultadoConta(
                codigo_conta="5.1.01",
                valor=Decimal("0"),
                indicador_dc="D",
            ),
        ),
        balanco=(
            LinhaDemonstracao("1.01", 2, "D", "Ativo Circulante", Decimal("1000.00")),
            LinhaDemonstracao("1", 1, "D", "ATIVO TOTAL", Decimal("1000.00")),
            LinhaDemonstracao("2.03", 2, "C", "Patrimônio Líquido", Decimal("1000.00")),
            LinhaDemonstracao("2", 1, "C", "PASSIVO + PL TOTAL", Decimal("1000.00")),
        ),
        dre=(
            LinhaDemonstracao("3.01", 2, "C", "Receita Bruta", Decimal("1000.00")),
            LinhaDemonstracao("3.14", 1, "C", "Lucro Líquido", Decimal("1000.00")),
        ),
    )


# ── Geração feliz ──────────────────────────────────────────────────────────


class TestGerarEcdHappyPath:
    def test_retorna_bytes_e_hash(self) -> None:
        out = gerar_ecd(_entrada_minima())
        assert isinstance(out.conteudo, bytes)
        assert len(out.hash_sha256) == 64
        assert out.tamanho_bytes == len(out.conteudo)
        assert out.algoritmo_versao == ALGORITMO_VERSAO
        assert out.leiaute_versao == "10.00"

    def test_arquivo_comeca_com_0000(self) -> None:
        out = gerar_ecd(_entrada_minima())
        texto = out.conteudo.decode("latin-1")
        assert texto.startswith("|0000|")

    def test_arquivo_termina_com_9999_e_lf(self) -> None:
        out = gerar_ecd(_entrada_minima())
        texto = out.conteudo.decode("latin-1")
        linhas = texto.splitlines(keepends=True)
        assert linhas[-1].startswith("|9999|")
        assert linhas[-1].endswith("|\n")

    def test_total_linhas_bate_com_9999(self) -> None:
        out = gerar_ecd(_entrada_minima())
        linhas = out.conteudo.decode("latin-1").splitlines()
        ultima = linhas[-1]
        total_declarado = int(ultima.split("|")[2])
        assert total_declarado == len(linhas)
        assert total_declarado == out.total_linhas

    def test_hash_estavel_entre_chamadas(self) -> None:
        e = _entrada_minima()
        h1 = gerar_ecd(e).hash_sha256
        h2 = gerar_ecd(e).hash_sha256
        assert h1 == h2

    def test_hash_muda_se_input_muda(self) -> None:
        e1 = _entrada_minima()
        # Trocar razão social muda o registro 0000 e logo o hash.
        empresa2 = IdentificacaoEmpresaEcd(
            cnpj=e1.empresa.cnpj,
            razao_social="Outra Razão LTDA",
            nome_fantasia=e1.empresa.nome_fantasia,
            uf=e1.empresa.uf,
            municipio=e1.empresa.municipio,
            codigo_municipio_ibge=e1.empresa.codigo_municipio_ibge,
        )
        e2 = EntradaEcd(
            empresa=empresa2,
            ano_calendario=e1.ano_calendario,
            inicio_exercicio=e1.inicio_exercicio,
            fim_exercicio=e1.fim_exercicio,
            plano_contas=e1.plano_contas,
            saldos_periodicos=e1.saldos_periodicos,
            lancamentos=e1.lancamentos,
            saldos_resultado_antes_encerramento=e1.saldos_resultado_antes_encerramento,
            balanco=e1.balanco,
            dre=e1.dre,
        )
        assert gerar_ecd(e1).hash_sha256 != gerar_ecd(e2).hash_sha256


# ── Estrutura por bloco ───────────────────────────────────────────────────


class TestEstruturaBlocos:
    def test_tem_todos_blocos_abertura_e_encerramento(self) -> None:
        out = gerar_ecd(_entrada_minima())
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines(keepends=True))
        # Cada bloco tem sua abertura e encerramento.
        for esperado in ("0000", "0001", "0990", "I001", "I990", "J001", "J990", "9999"):
            assert regs.get(esperado, 0) >= 1, f"Registro {esperado} ausente"

    def test_i050_uma_linha_por_conta(self) -> None:
        out = gerar_ecd(_entrada_minima())
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines(keepends=True))
        assert regs["I050"] == len(_plano_minimo())

    def test_i051_mapping_referencial_apenas_analiticas(self) -> None:
        out = gerar_ecd(_entrada_minima())
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines(keepends=True))
        analiticas_com_ref = sum(
            1 for c in _plano_minimo()
            if c.tipo_conta == "A" and c.codigo_ecd_referencial
        )
        assert regs["I051"] == analiticas_com_ref

    def test_i200_e_i250_por_lancamento(self) -> None:
        out = gerar_ecd(_entrada_minima())
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines(keepends=True))
        # 1 lançamento, 2 partidas.
        assert regs["I200"] == 1
        assert regs["I250"] == 2

    def test_j100_uma_linha_por_agrupamento_balanco(self) -> None:
        e = _entrada_minima()
        out = gerar_ecd(e)
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines(keepends=True))
        assert regs["J100"] == len(e.balanco)

    def test_j150_uma_linha_por_agrupamento_dre(self) -> None:
        e = _entrada_minima()
        out = gerar_ecd(e)
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines(keepends=True))
        assert regs["J150"] == len(e.dre)

    def test_9900_consistente_com_arquivo(self) -> None:
        out = gerar_ecd(_entrada_minima())
        linhas = out.conteudo.decode("latin-1").splitlines(keepends=True)
        contagem_real = contar_registros(linhas)
        # Cada 9900 vai conter (REG, contagem). Verificar todos.
        for ln in linhas:
            if not ln.startswith("|9900|"):
                continue
            campos = ln.strip().split("|")
            tipo = campos[2]
            declarada = int(campos[3])
            assert contagem_real.get(tipo) == declarada


# ── Validações de pré-condição ─────────────────────────────────────────────


class TestValidacoes:
    def test_cnpj_invalido_levanta(self) -> None:
        e = _entrada_minima()
        empresa_ruim = IdentificacaoEmpresaEcd(
            cnpj="123",
            razao_social="X",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="3550308",
        )
        entrada_ruim = EntradaEcd(
            empresa=empresa_ruim,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            plano_contas=e.plano_contas,
            saldos_periodicos=e.saldos_periodicos,
            lancamentos=e.lancamentos,
            saldos_resultado_antes_encerramento=e.saldos_resultado_antes_encerramento,
            balanco=e.balanco,
            dre=e.dre,
        )
        with pytest.raises(_EntradaEcdInvalida, match="CNPJ"):
            gerar_ecd(entrada_ruim)

    def test_ibge_curto_levanta(self) -> None:
        e = _entrada_minima()
        empresa_ruim = IdentificacaoEmpresaEcd(
            cnpj="12345678000190",
            razao_social="X",
            nome_fantasia=None,
            uf="SP",
            municipio=None,
            codigo_municipio_ibge="123",
        )
        entrada_ruim = EntradaEcd(
            empresa=empresa_ruim,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            plano_contas=e.plano_contas,
            saldos_periodicos=e.saldos_periodicos,
            lancamentos=e.lancamentos,
            saldos_resultado_antes_encerramento=e.saldos_resultado_antes_encerramento,
            balanco=e.balanco,
            dre=e.dre,
        )
        with pytest.raises(_EntradaEcdInvalida, match="IBGE"):
            gerar_ecd(entrada_ruim)

    def test_lancamento_desbalanceado_levanta(self) -> None:
        # Débito R$ 1000 e crédito R$ 999 — pega na validação.
        desbalanceado = LancamentoEcd(
            numero="1",
            data=date(2025, 3, 15),
            valor_total=Decimal("1000.00"),
            indicador_origem="N",
            partidas=(
                PartidaLanc(
                    codigo_conta="1.1.1.01",
                    valor=Decimal("1000.00"),
                    indicador_dc="D",
                    historico="x",
                ),
                PartidaLanc(
                    codigo_conta="4.1.01",
                    valor=Decimal("999.00"),
                    indicador_dc="C",
                    historico="x",
                ),
            ),
        )
        entrada = _entrada_minima(lancamentos=(desbalanceado,))
        with pytest.raises(_EntradaEcdInvalida, match="débitos"):
            gerar_ecd(entrada)

    def test_valor_total_divergente_levanta(self) -> None:
        # Partidas balanceadas em 999 mas valor_total declarado 1000.
        divergente = LancamentoEcd(
            numero="1",
            data=date(2025, 3, 15),
            valor_total=Decimal("1000.00"),
            indicador_origem="N",
            partidas=(
                PartidaLanc(
                    codigo_conta="1.1.1.01",
                    valor=Decimal("999.00"),
                    indicador_dc="D",
                    historico="x",
                ),
                PartidaLanc(
                    codigo_conta="4.1.01",
                    valor=Decimal("999.00"),
                    indicador_dc="C",
                    historico="x",
                ),
            ),
        )
        entrada = _entrada_minima(lancamentos=(divergente,))
        with pytest.raises(_EntradaEcdInvalida, match="valor_total"):
            gerar_ecd(entrada)

    def test_partida_com_conta_fora_do_plano_levanta(self) -> None:
        ruim = LancamentoEcd(
            numero="1",
            data=date(2025, 3, 15),
            valor_total=Decimal("100.00"),
            indicador_origem="N",
            partidas=(
                PartidaLanc(
                    codigo_conta="9.9.9.99",  # ← não existe no plano
                    valor=Decimal("100.00"),
                    indicador_dc="D",
                    historico="x",
                ),
                PartidaLanc(
                    codigo_conta="4.1.01",
                    valor=Decimal("100.00"),
                    indicador_dc="C",
                    historico="x",
                ),
            ),
        )
        entrada = _entrada_minima(lancamentos=(ruim,))
        with pytest.raises(_EntradaEcdInvalida, match="ausente do plano"):
            gerar_ecd(entrada)

    def test_fim_antes_de_inicio_levanta(self) -> None:
        e = _entrada_minima()
        entrada = EntradaEcd(
            empresa=e.empresa,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=date(2025, 12, 31),
            fim_exercicio=date(2025, 1, 1),
            plano_contas=e.plano_contas,
            saldos_periodicos=e.saldos_periodicos,
            lancamentos=e.lancamentos,
            saldos_resultado_antes_encerramento=e.saldos_resultado_antes_encerramento,
            balanco=e.balanco,
            dre=e.dre,
        )
        with pytest.raises(_EntradaEcdInvalida, match="fim_exercicio"):
            gerar_ecd(entrada)

    def test_tipo_escrituracao_invalido_levanta(self) -> None:
        e = _entrada_minima()
        entrada = EntradaEcd(
            empresa=e.empresa,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            plano_contas=e.plano_contas,
            saldos_periodicos=e.saldos_periodicos,
            lancamentos=e.lancamentos,
            saldos_resultado_antes_encerramento=e.saldos_resultado_antes_encerramento,
            balanco=e.balanco,
            dre=e.dre,
            tipo_escrituracao="X",  # ← inválido
        )
        with pytest.raises(_EntradaEcdInvalida, match="tipo_escrituracao"):
            gerar_ecd(entrada)


# ── Conteúdo determinístico mínimo ─────────────────────────────────────────


class TestConteudoDeterministico:
    def test_0000_tem_cnpj_no_campo_correto(self) -> None:
        out = gerar_ecd(_entrada_minima())
        linha_0000 = out.conteudo.decode("latin-1").splitlines()[0]
        # Layout: |0000|VERSAO|SIT_INI|NUM_REC|DT_INI|DT_FIN|NOME|CNPJ|UF|...
        campos = linha_0000.split("|")
        # campos[0]='' (pipe inicial), campos[1]='0000', ..., campos[8]=CNPJ
        assert campos[8] == "12345678000190"

    def test_i050_tem_codigo_e_descricao_no_lugar(self) -> None:
        out = gerar_ecd(_entrada_minima())
        linhas = out.conteudo.decode("latin-1").splitlines()
        i050_caixa = next(ln for ln in linhas if "|I050|" in ln and "Caixa" in ln)
        # Layout I050: |I050|DT_ALT|COD_NAT|IND_CTA|NIVEL|COD_NAT(natur)|COD_CTA|COD_CTA_SUP|CTA|
        campos = i050_caixa.split("|")
        assert campos[7] == "1.1.1.01"
        assert campos[9] == "Caixa"

    def test_i250_partidas_com_dc_correto(self) -> None:
        out = gerar_ecd(_entrada_minima())
        linhas = out.conteudo.decode("latin-1").splitlines()
        i250 = [ln for ln in linhas if ln.startswith("|I250|")]
        assert len(i250) == 2
        # I250: |I250|COD_CTA|COD_CCUS|VL|IND_DC|HISTÓRICO|HIST_PAD|
        # Primeira partida = débito caixa.
        primeira = i250[0].split("|")
        assert primeira[2] == "1.1.1.01"
        assert primeira[4] == "1000,00"
        assert primeira[5] == "D"

    def test_codifica_em_latin1(self) -> None:
        # Razão social com acentos — codifica e decodifica em latin-1.
        out = gerar_ecd(_entrada_minima())
        texto = out.conteudo.decode("latin-1")
        # "Comércio" aparece na razão social (registro 0000).
        assert "Comércio Modelo LTDA" in texto


# ── Ano sem lançamentos (extremo) ─────────────────────────────────────────


class TestArquivoSemMovimento:
    def test_gera_arquivo_minimo_sem_lancamentos(self) -> None:
        """Empresa que abriu mas não escriturou: arquivo só com blocos de abertura.

        Aceita lista vazia de lançamentos — útil para empresa em pré-operação
        ou exercício especial sem operações. O service usa esta validação
        como guarda extra (``SemDadosParaSped``), mas o gerador puro permite.
        """
        e = _entrada_minima()
        sem_movimento = EntradaEcd(
            empresa=e.empresa,
            ano_calendario=e.ano_calendario,
            inicio_exercicio=e.inicio_exercicio,
            fim_exercicio=e.fim_exercicio,
            plano_contas=e.plano_contas,
            saldos_periodicos=(),
            lancamentos=(),
            saldos_resultado_antes_encerramento=(),
            balanco=e.balanco,
            dre=e.dre,
        )
        out = gerar_ecd(sem_movimento)
        regs = contar_registros(out.conteudo.decode("latin-1").splitlines(keepends=True))
        assert regs.get("I200", 0) == 0
        assert regs.get("I250", 0) == 0
        # Bloco I ainda existe — só não tem lançamentos.
        assert regs["I001"] == 1
        assert regs["I990"] == 1
        # Arquivo válido — 9999 fecha.
        assert regs["9999"] == 1
