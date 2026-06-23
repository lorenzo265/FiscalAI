"""Testes unitários do PgdasService + helpers puros (Sprint 6 PR2)."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.pgdas.schemas import TransmissaoStatus
from app.modules.pgdas.service import (
    PgdasService,
    _extrair_protocolo_e_recibo,
    _gerar_idempotency_key,
    _montar_payload_declaracao,
)
from app.shared.exceptions import (
    ApuracaoNaoEncontrada,
    EmpresaNaoEncontrada,
    RegimeIncompativel,
    SerproErro,
)


def _empresa_sn(codigo_ibge: str | None = "3550308") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        cnpj="12345678000195",
        regime_tributario="simples_nacional",
        anexo_simples="III",
        municipio="São Paulo",
        codigo_municipio_ibge=codigo_ibge,
        uf="SP",
    )


def _apuracao_das(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        competencia=date(2026, 4, 1),
        tipo="das",
        # input_jsonb sem massa_salarial_12m — simula apuração pré-v4 (retrocompat).
        # Testes do Achado #4 que precisam do campo populam manualmente após criar.
        input_jsonb={
            "rbt12": "500000.00",
            "receita_mes": "10000.00",
            "folha_12m": None,
            "encargos_folha_12m": "0",
            "competencia": "2026-04",
        },
        output_jsonb={
            "anexo": "III",
            "anexo_efetivo": "III",
            "receita_mes": "10000.00",
            "valor_das": "650.00",
        },
        transmitido_em=None,
        status="calculado",
    )


# ── helpers puros ────────────────────────────────────────────────────────────


class TestGerarIdempotencyKey:
    def test_deterministico_mesmos_inputs(self) -> None:
        eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        c = date(2026, 4, 1)
        k1 = _gerar_idempotency_key(eid, c, 1, False)
        k2 = _gerar_idempotency_key(eid, c, 1, False)
        assert k1 == k2

    def test_retificadora_muda_key(self) -> None:
        eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        c = date(2026, 4, 1)
        original = _gerar_idempotency_key(eid, c, 1, False)
        retif = _gerar_idempotency_key(eid, c, 1, True)
        assert original != retif

    def test_tentativa_diferente_muda_key(self) -> None:
        eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        c = date(2026, 4, 1)
        k1 = _gerar_idempotency_key(eid, c, 1, False)
        k2 = _gerar_idempotency_key(eid, c, 2, False)
        assert k1 != k2


class TestMontarPayload:
    def test_estrutura_basica(self) -> None:
        empresa = _empresa_sn()
        apuracao = _apuracao_das(empresa.id)
        payload = _montar_payload_declaracao(empresa, apuracao)
        decl = payload["declaracao"]
        assert decl["tipoDeclaracao"] == 1
        assert decl["receitaPaCompetencia"] == "10000.00"
        assert decl["estabelecimentos"][0]["cnpjCompleto"] == "12345678000195"
        atividade = decl["estabelecimentos"][0]["atividades"][0]
        # Sprint 19.6 PR2 (#16): Anexo III mapeia para idAtividade 4
        # (Manual SERPRO v1.4+ — serviços ISS, não 3 que é locação).
        assert atividade["idAtividade"] == 4
        assert atividade["valorAtividade"] == "10000.00"

    def test_anexo_i_mapeia_comercio(self) -> None:
        empresa = _empresa_sn()
        empresa.anexo_simples = "I"
        apuracao = _apuracao_das(empresa.id)
        apuracao.output_jsonb["anexo_efetivo"] = "I"
        payload = _montar_payload_declaracao(empresa, apuracao)
        ativ = payload["declaracao"]["estabelecimentos"][0]["atividades"][0]
        assert ativ["idAtividade"] == 1

    def test_municipio_no_payload_usa_ibge_nao_nome(self) -> None:
        """SERPRO PGDAS-D exige código IBGE 7-dígitos no campo `municipio`."""
        empresa = _empresa_sn()
        apuracao = _apuracao_das(empresa.id)
        payload = _montar_payload_declaracao(empresa, apuracao)
        receita = payload["declaracao"]["estabelecimentos"][0]["atividades"][0][
            "receitasAtividade"
        ][0]
        # Vai o IBGE "3550308", nunca o nome "São Paulo"
        assert receita["municipio"] == "3550308"
        assert receita["uf"] == "SP"

    def test_multi_anexo_gera_uma_atividade_por_anexo(self) -> None:
        """v3: ``receitas_por_anexo`` no output_jsonb produz múltiplas atividades."""
        empresa = _empresa_sn()
        apuracao = _apuracao_das(empresa.id)
        apuracao.output_jsonb["receita_mes"] = "15000.00"
        apuracao.output_jsonb["receitas_por_anexo"] = {
            "I": "10000.00",
            "III": "5000.00",
        }
        payload = _montar_payload_declaracao(empresa, apuracao)
        atividades = payload["declaracao"]["estabelecimentos"][0]["atividades"]
        assert len(atividades) == 2

        # Ordem determinística (sorted) — I antes de III
        # Sprint 19.6 PR2 (#16): Anexo III = idAtividade 4 (Manual v1.4+).
        assert atividades[0]["idAtividade"] == 1
        assert atividades[0]["valorAtividade"] == "10000.00"
        assert atividades[1]["idAtividade"] == 4
        assert atividades[1]["valorAtividade"] == "5000.00"

        # receitaPaCompetencia mantém o total
        assert payload["declaracao"]["receitaPaCompetencia"] == "15000.00"

    def test_multi_anexo_descarta_zero(self) -> None:
        """Anexos com receita 0 no jsonb não viram atividade."""
        empresa = _empresa_sn()
        apuracao = _apuracao_das(empresa.id)
        apuracao.output_jsonb["receitas_por_anexo"] = {
            "I": "8000.00",
            "II": "0.00",
            "III": "2000.00",
        }
        payload = _montar_payload_declaracao(empresa, apuracao)
        atividades = payload["declaracao"]["estabelecimentos"][0]["atividades"]
        # Sprint 19.6 PR2 (#16): {Anexo I=1, Anexo III=4} (Manual v1.4+).
        assert {a["idAtividade"] for a in atividades} == {1, 4}

    def test_compat_pre_v3_apuracao_sem_receitas_por_anexo(self) -> None:
        """Apuração antiga (sn.das.v2) sem receitas_por_anexo cai no fallback."""
        empresa = _empresa_sn()
        apuracao = _apuracao_das(empresa.id)
        # Garante que NÃO existe receitas_por_anexo (cenário pré-v3)
        apuracao.output_jsonb.pop("receitas_por_anexo", None)
        payload = _montar_payload_declaracao(empresa, apuracao)
        atividades = payload["declaracao"]["estabelecimentos"][0]["atividades"]
        # Comportamento idêntico ao PR2 original: 1 atividade do anexo_efetivo.
        # Sprint 19.6 PR2 (#16): Anexo III = idAtividade 4 (Manual v1.4+).
        assert len(atividades) == 1
        assert atividades[0]["idAtividade"] == 4
        assert atividades[0]["valorAtividade"] == "10000.00"


# ── Manual SERPRO PGDAS-D v1.4+ — idAtividade (Sprint 19.6 PR2 #16) ────────


from app.modules.pgdas.service import (  # noqa: E402
    _competencia_anterior,
    _id_atividade_por_anexo,
    _montar_folhas_salario,
)


class TestIdAtividadePorAnexo:
    """Mapa Manual SERPRO v1.4+: 1=Comércio, 2=Indústria, 3=Locação,
    4=Serviços ISS, 5=Anexo IV (construção), 6=Anexo V (técnicos),
    7=Trib. concentrada, 8=Exportação.
    """

    def test_anexo_i_revenda_mercadorias(self) -> None:
        assert _id_atividade_por_anexo("I") == 1

    def test_anexo_ii_industria(self) -> None:
        assert _id_atividade_por_anexo("II") == 2

    def test_anexo_iii_servicos_iss_padrao(self) -> None:
        """Anexo III sem subtipo = idAtividade 4 (serviços ISS — caso comum)."""
        assert _id_atividade_por_anexo("III") == 4

    def test_anexo_iv_construcao(self) -> None:
        assert _id_atividade_por_anexo("IV") == 5

    def test_anexo_v_servicos_tecnicos(self) -> None:
        assert _id_atividade_por_anexo("V") == 6

    def test_subtipo_locacao_bens_moveis_override(self) -> None:
        """Override de subtipo: locação dentro do Anexo III = idAtividade 3."""
        assert _id_atividade_por_anexo(
            "III", subtipo="locacao_bens_moveis"
        ) == 3

    def test_subtipo_exportacao_override(self) -> None:
        assert _id_atividade_por_anexo("I", subtipo="exportacao") == 8

    def test_subtipo_tributacao_concentrada_override(self) -> None:
        assert _id_atividade_por_anexo(
            "I", subtipo="tributacao_concentrada"
        ) == 7

    def test_subtipo_desconhecido_cai_no_padrao_do_anexo(self) -> None:
        """Subtipo não cadastrado é ignorado — usa código do anexo."""
        assert _id_atividade_por_anexo("III", subtipo="inexistente") == 4

    def test_anexo_desconhecido_cai_em_1(self) -> None:
        """Fallback defensivo — anexo inválido (e.g. importação errada) = 1."""
        assert _id_atividade_por_anexo("X") == 1


class TestExtrairProtocolo:
    def test_dados_dict(self) -> None:
        resposta = {"dados": {"numeroDeclaracao": "ABC-001"}}
        protocolo, _ = _extrair_protocolo_e_recibo(resposta)
        assert protocolo == "ABC-001"

    def test_dados_string_json(self) -> None:
        resposta = {"dados": '{"numeroDeclaracao": "ABC-002"}'}
        protocolo, _ = _extrair_protocolo_e_recibo(resposta)
        assert protocolo == "ABC-002"

    def test_sem_protocolo(self) -> None:
        protocolo, _ = _extrair_protocolo_e_recibo({"dados": {}})
        assert protocolo is None

    def test_com_recibo_b64_gera_storage_key(self) -> None:
        resposta = {"dados": {"numeroDeclaracao": "001", "recibo": "JVB="}}
        protocolo, recibo = _extrair_protocolo_e_recibo(resposta)
        assert protocolo == "001"
        assert recibo == "pgdas/001.pdf"


# ── service.transmitir ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo), pytest.raises(EmpresaNaoEncontrada):
        await PgdasService().transmitir(
            session,
            uuid.uuid4(),
            uuid.uuid4(),
            date(2026, 4, 1),
            eh_retificadora=False,
            serpro_client=AsyncMock(),
        )


@pytest.mark.asyncio
async def test_transmitir_sem_ibge_levanta() -> None:
    """Sem `codigo_municipio_ibge`, transmissão levanta MunicipioIbgeAusente."""
    from app.shared.exceptions import MunicipioIbgeAusente

    session = AsyncMock()
    empresa = _empresa_sn(codigo_ibge=None)
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    with patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo):
        with pytest.raises(MunicipioIbgeAusente) as exc_info:
            await PgdasService().transmitir(
                session,
                uuid.uuid4(),
                empresa.id,
                date(2026, 4, 1),
                eh_retificadora=False,
                serpro_client=AsyncMock(),
            )
        assert exc_info.value.http_status == 422


@pytest.mark.asyncio
async def test_transmitir_regime_lp_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa_sn()
    empresa.regime_tributario = "lucro_presumido"
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    with patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo), pytest.raises(RegimeIncompativel):
        await PgdasService().transmitir(
            session,
            uuid.uuid4(),
            empresa.id,
            date(2026, 4, 1),
            eh_retificadora=False,
            serpro_client=AsyncMock(),
        )


@pytest.mark.asyncio
async def test_transmitir_sem_apuracao_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa_sn()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.buscar = AsyncMock(return_value=None)

    with (
        patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.pgdas.service.ApuracaoFiscalRepo",
            return_value=apuracao_repo,
        ),
        pytest.raises(ApuracaoNaoEncontrada),
    ):
        await PgdasService().transmitir(
            session,
            uuid.uuid4(),
            empresa.id,
            date(2026, 4, 1),
            eh_retificadora=False,
            serpro_client=AsyncMock(),
        )


@pytest.mark.asyncio
async def test_transmissao_sucesso_atualiza_apuracao() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa_sn()
    apuracao = _apuracao_das(empresa.id)

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.buscar = AsyncMock(return_value=apuracao)

    tr_id = uuid.uuid4()
    transmissoes = AsyncMock()
    transmissoes.proxima_tentativa = AsyncMock(return_value=1)
    transmissoes.criar = AsyncMock(return_value=SimpleNamespace(id=tr_id))
    transmissoes.marcar_sucesso = AsyncMock()

    serpro = AsyncMock()
    serpro.transmitir_pgdas_d = AsyncMock(
        return_value={"dados": {"numeroDeclaracao": "PGDAS-2026-04-001"}}
    )

    with (
        patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.pgdas.service.ApuracaoFiscalRepo", return_value=apuracao_repo
        ),
        patch(
            "app.modules.pgdas.service.TransmissoesPgdasRepo",
            return_value=transmissoes,
        ),
    ):
        out = await PgdasService().transmitir(
            session,
            uuid.uuid4(),
            empresa.id,
            apuracao.competencia,
            eh_retificadora=False,
            serpro_client=serpro,
        )

    assert out.status == TransmissaoStatus.TRANSMITIDA
    assert out.protocolo == "PGDAS-2026-04-001"
    assert apuracao.status == "transmitida"
    assert apuracao.transmitido_em is not None
    transmissoes.marcar_sucesso.assert_awaited_once()


@pytest.mark.asyncio
async def test_transmissao_falha_serpro_marca_erro() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa_sn()
    apuracao = _apuracao_das(empresa.id)

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.buscar = AsyncMock(return_value=apuracao)

    transmissoes = AsyncMock()
    transmissoes.proxima_tentativa = AsyncMock(return_value=1)
    transmissoes.criar = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    transmissoes.marcar_erro = AsyncMock()

    serpro = AsyncMock()
    serpro.transmitir_pgdas_d = AsyncMock(side_effect=SerproErro("422 inválido"))

    with (
        patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.pgdas.service.ApuracaoFiscalRepo", return_value=apuracao_repo
        ),
        patch(
            "app.modules.pgdas.service.TransmissoesPgdasRepo",
            return_value=transmissoes,
        ),
    ):
        out = await PgdasService().transmitir(
            session,
            uuid.uuid4(),
            empresa.id,
            apuracao.competencia,
            eh_retificadora=False,
            serpro_client=serpro,
        )

    assert out.status == TransmissaoStatus.ERRO
    assert out.erro == "SerproErro"
    transmissoes.marcar_erro.assert_awaited_once()
    # Apuração NÃO deve ser marcada como transmitida em caso de erro
    assert apuracao.status == "calculado"


@pytest.mark.asyncio
async def test_retificacao_sem_transmissao_previa_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa_sn()
    apuracao = _apuracao_das(empresa.id)

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.buscar = AsyncMock(return_value=apuracao)

    transmissoes = AsyncMock()
    transmissoes.ultima_transmissao = AsyncMock(return_value=None)

    from app.shared.exceptions import RetificacaoSemOriginal

    with (
        patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.pgdas.service.ApuracaoFiscalRepo", return_value=apuracao_repo
        ),
        patch(
            "app.modules.pgdas.service.TransmissoesPgdasRepo",
            return_value=transmissoes,
        ),
    ):
        # m4 da auditoria: RetificacaoSemOriginal (409) é semanticamente correto
        with pytest.raises(RetificacaoSemOriginal) as exc_info:
            await PgdasService().transmitir(
                session,
                uuid.uuid4(),
                empresa.id,
                apuracao.competencia,
                eh_retificadora=True,
                serpro_client=AsyncMock(),
            )
        assert exc_info.value.http_status == 409


# ── Achado #4 — PGDAS transmite folhasSalario vazio (auditoria 2026-06-21) ───
#
# Fonte: LC 123/2006 art. 18 §5º-J; Res. CGSN 140/2018 art. 26 §1º;
# Manual PGDAS-D SERPRO (referência ao campo folhasSalario).
#
# O SERPRO recalcula o Fator R internamente a partir da folha declarada no payload.
# Se folhasSalario=[], o SERPRO resolve como se massa=0 → Fator R=0 → Anexo V,
# divergindo do Fator R calculado internamente que pode ter resolvido Anexo III.
#
# Correção: _montar_folhas_salario() preenche folhasSalario para Anexo III/V
# com a massa_salarial_12m do input_jsonb (remuneração + CPP + FGTS + 13º),
# distribuída uniformemente pelas 12 competências anteriores à apuração.
#
# SUPOSIÇÃO DE FORMATO: {"competencia": "AAAAMM", "valorFolha": "0.00"}.
# Confirmar contra o Manual SERPRO real antes de habilitar em produção.


class TestCompetenciaAnterior:
    """Testa a aritmética de subtração de meses para geração das competências."""

    def test_um_mes_antes(self) -> None:
        ref = date(2026, 4, 1)
        assert _competencia_anterior(ref, 1) == "202603"

    def test_doze_meses_antes(self) -> None:
        ref = date(2026, 4, 1)
        assert _competencia_anterior(ref, 12) == "202504"

    def test_virada_de_ano(self) -> None:
        ref = date(2026, 1, 1)
        assert _competencia_anterior(ref, 1) == "202512"

    def test_dois_anos_antes(self) -> None:
        ref = date(2026, 3, 1)
        assert _competencia_anterior(ref, 24) == "202403"


class TestMontarFolhasSalario:
    """Testa _montar_folhas_salario — construtor do campo folhasSalario do PGDAS-D."""

    def test_anexo_iii_com_massa_gera_12_itens(self) -> None:
        """Anexo III com massa_salarial_12m preenche 12 meses de folha."""
        folhas = _montar_folhas_salario(
            apuracao_competencia=date(2026, 4, 1),
            anexo_efetivo="III",
            input_jsonb={"massa_salarial_12m": "120000.00"},
        )
        assert len(folhas) == 12

    def test_anexo_v_com_massa_gera_12_itens(self) -> None:
        """Anexo V também usa Fator R — deve preencher folha."""
        folhas = _montar_folhas_salario(
            apuracao_competencia=date(2026, 4, 1),
            anexo_efetivo="V",
            input_jsonb={"massa_salarial_12m": "60000.00"},
        )
        assert len(folhas) == 12

    def test_anexo_i_retorna_vazio(self) -> None:
        """Anexo I não usa Fator R — folhasSalario deve ser []."""
        folhas = _montar_folhas_salario(
            apuracao_competencia=date(2026, 4, 1),
            anexo_efetivo="I",
            input_jsonb={"massa_salarial_12m": "120000.00"},
        )
        assert folhas == []

    def test_sem_massa_no_input_jsonb_retorna_vazio(self) -> None:
        """Apuração pré-v4 sem massa_salarial_12m — comportamento anterior mantido."""
        folhas = _montar_folhas_salario(
            apuracao_competencia=date(2026, 4, 1),
            anexo_efetivo="III",
            input_jsonb={},  # pré-v4: sem o campo
        )
        assert folhas == []

    def test_massa_zero_retorna_vazio(self) -> None:
        """Massa zero não deve gerar itens (empresa sem funcionários declarando III)."""
        folhas = _montar_folhas_salario(
            apuracao_competencia=date(2026, 4, 1),
            anexo_efetivo="III",
            input_jsonb={"massa_salarial_12m": "0.00"},
        )
        assert folhas == []

    def test_soma_das_folhas_bate_massa_total(self) -> None:
        """A soma dos 12 valorFolha deve igualar massa_salarial_12m (tolerância 1 centavo).

        Garante que a distribuição uniforme + ajuste de arredondamento não perde
        nem inventa centavos na transmissão ao SERPRO.
        """
        from decimal import Decimal as D

        massa = D("120000.01")  # valor propositalmente não divisível por 12
        folhas = _montar_folhas_salario(
            apuracao_competencia=date(2026, 4, 1),
            anexo_efetivo="III",
            input_jsonb={"massa_salarial_12m": str(massa)},
        )
        soma = sum(D(f["valorFolha"]) for f in folhas)  # type: ignore[arg-type]
        assert abs(soma - massa) <= D("0.01"), (
            f"Soma das folhas R${soma} difere da massa R${massa} por mais de R$0,01"
        )

    def test_competencias_sao_os_12_meses_anteriores(self) -> None:
        """As 12 competências devem ser exatamente os 12 meses anteriores à apuração."""
        folhas = _montar_folhas_salario(
            apuracao_competencia=date(2026, 4, 1),
            anexo_efetivo="III",
            input_jsonb={"massa_salarial_12m": "120000.00"},
        )
        competencias = [str(f["competencia"]) for f in folhas]  # type: ignore[index]
        # Meses anteriores: de 12 meses atrás até 1 mês atrás
        esperadas = [
            "202504",  # 12 meses antes de abr/2026 = abr/2025
            "202505", "202506", "202507", "202508", "202509",
            "202510", "202511", "202512", "202601", "202602", "202603",
        ]
        assert competencias == esperadas

    def test_formato_chaves_do_item(self) -> None:
        """Cada item deve ter exatamente as chaves 'competencia' e 'valorFolha'."""
        folhas = _montar_folhas_salario(
            apuracao_competencia=date(2026, 4, 1),
            anexo_efetivo="III",
            input_jsonb={"massa_salarial_12m": "60000.00"},
        )
        for item in folhas:
            assert set(item.keys()) == {"competencia", "valorFolha"}, (
                f"Item com chaves inesperadas: {set(item.keys())}"
            )


class TestReconciliacaoPgdasVsDasInterno:
    """Golden de reconciliação: o anexo no payload PGDAS deve igualar o anexo
    calculado internamente (evitar divergência com o SERPRO).

    Prova do Achado #4: antes da correção, folhasSalario=[] fazia o SERPRO
    resolver Fator R como 0 → Anexo V, mesmo que internamente tivéssemos
    calculado Anexo III. Com a correção, o campo é preenchido com a massa
    salarial real → SERPRO e sistema convergem no mesmo anexo.
    """

    def _apuracao_com_massa(
        self,
        empresa_id: uuid.UUID,
        anexo_efetivo: str,
        massa_salarial_12m: str,
    ) -> SimpleNamespace:
        """Cria uma apuração simulada com input_jsonb populado (pós-v4)."""
        return SimpleNamespace(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            competencia=date(2026, 4, 1),
            tipo="das",
            input_jsonb={
                "rbt12": "500000.00",
                "receita_mes": "40000.00",
                "folha_12m": "130000.00",
                "encargos_folha_12m": "15000.00",
                "massa_salarial_12m": massa_salarial_12m,
                "competencia": "2026-04",
            },
            output_jsonb={
                "anexo": "III",
                "anexo_efetivo": anexo_efetivo,
                "receita_mes": "40000.00",
                "valor_das": "3636.00",
                "fator_r": "0.29",
            },
            transmitido_em=None,
            status="calculado",
        )

    def test_anexo_iii_payload_contem_folhas_nao_vazias(self) -> None:
        """Empresa Anexo III com massa_salarial_12m → folhasSalario não é [].

        Antes da correção (Achado #4): sempre [].
        Após a correção: lista de 12 itens com a massa distribuída.
        """
        empresa = _empresa_sn()
        apuracao = self._apuracao_com_massa(
            empresa.id, "III", "145000.00"
        )
        payload = _montar_payload_declaracao(empresa, apuracao)
        folhas = payload["declaracao"]["folhasSalario"]

        assert isinstance(folhas, list)
        assert len(folhas) == 12, (
            "PGDAS-D deve declarar 12 meses de folha para Anexo III "
            "para que o SERPRO calcule Fator R corretamente"
        )

    def test_anexo_iii_soma_folhas_bate_massa(self) -> None:
        """A soma das folhas no payload deve igualar a massa salarial da apuração.

        Esta é a prova formal de reconciliação: massa usada internamente no
        cálculo do Fator R == massa enviada ao SERPRO no payload PGDAS-D.
        """
        from decimal import Decimal as D

        massa = "145000.00"
        empresa = _empresa_sn()
        apuracao = self._apuracao_com_massa(empresa.id, "III", massa)
        payload = _montar_payload_declaracao(empresa, apuracao)
        folhas = payload["declaracao"]["folhasSalario"]

        soma = sum(D(str(f["valorFolha"])) for f in folhas)
        assert abs(soma - D(massa)) <= D("0.01"), (
            f"Soma folhas PGDAS R${soma} diverge da massa interna R${massa}. "
            "SERPRO recalcularia Fator R diferente do calculado internamente."
        )

    def test_pre_v4_sem_massa_envia_lista_vazia_compat(self) -> None:
        """Apuração pré-v4 sem massa_salarial_12m → folhasSalario=[] (compat).

        Mantém o comportamento anterior — divergência com SERPRO persiste
        mas não é piorada. O warning deve ser dado no frontend ao contador.
        """
        empresa = _empresa_sn()
        apuracao = _apuracao_das(empresa.id)  # fixture sem input_jsonb massa
        payload = _montar_payload_declaracao(empresa, apuracao)
        # Garante retrocompatibilidade: antes da v4, folhasSalario era []
        assert payload["declaracao"]["folhasSalario"] == []

    def test_anexo_i_nao_declara_folha(self) -> None:
        """Empresa Anexo I não usa Fator R — folhasSalario deve ser []."""
        empresa = _empresa_sn()
        empresa.anexo_simples = "I"
        apuracao = _apuracao_das(empresa.id)
        apuracao.output_jsonb["anexo_efetivo"] = "I"
        apuracao.input_jsonb = {"massa_salarial_12m": "50000.00"}
        payload = _montar_payload_declaracao(empresa, apuracao)
        assert payload["declaracao"]["folhasSalario"] == []
