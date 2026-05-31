"""Testes unitários — builder de payload NFS-e e geração de focus_ref."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.notas.schemas import EmitirNfseIn, EmitirNfseOut
from app.modules.notas.service import _construir_payload_focus, _gerar_focus_ref


class TestGerarFocusRef:
    def test_determinismo(self) -> None:
        empresa_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        ref1 = _gerar_focus_ref(empresa_id, "001")
        ref2 = _gerar_focus_ref(empresa_id, "001")
        assert ref1 == ref2

    def test_diferentes_rps_geram_refs_diferentes(self) -> None:
        empresa_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        ref1 = _gerar_focus_ref(empresa_id, "001")
        ref2 = _gerar_focus_ref(empresa_id, "002")
        assert ref1 != ref2

    def test_diferentes_empresas_geram_refs_diferentes(self) -> None:
        eid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        eid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        ref1 = _gerar_focus_ref(eid1, "001")
        ref2 = _gerar_focus_ref(eid2, "001")
        assert ref1 != ref2

    def test_formato_uuid(self) -> None:
        ref = _gerar_focus_ref(uuid.uuid4(), "001")
        parsed = uuid.UUID(ref)
        assert str(parsed) == ref


class TestConstruirPayloadFocus:
    def _empresa(self) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(
            cnpj="12345678000195",
            im="123456",
            municipio="São Paulo",
            codigo_municipio_ibge="3550308",  # IBGE São Paulo
        )

    def _payload(
        self,
        valor: str = "1000.00",
        aliquota: str = "2.00",
        deducoes: str = "0.00",
    ) -> EmitirNfseIn:
        return EmitirNfseIn(
            natureza_operacao=1,
            servico_descricao="Desenvolvimento de sistema de gestão fiscal",
            servico_codigo="01.07",
            servico_valor=Decimal(valor),
            aliquota_iss=Decimal(aliquota),
            deducoes=Decimal(deducoes),
        )

    def test_estrutura_basica(self) -> None:
        empresa = self._empresa()
        payload = self._payload()
        data = _construir_payload_focus(empresa, payload, "001")  # type: ignore[arg-type]

        assert "prestador" in data
        assert "servico" in data
        assert data["prestador"]["cnpj"] == "12345678000195"
        assert data["numero_rps"] == "001"

    def test_codigo_municipio_usa_ibge_nao_nome(self) -> None:
        """Focus NFe exige código IBGE 7-dígitos, nunca nome do município."""
        empresa = self._empresa()
        payload = self._payload()
        data = _construir_payload_focus(empresa, payload, "001")  # type: ignore[arg-type]

        # IBGE 7-dígitos vai para codigo_municipio (não "São Paulo")
        assert data["prestador"]["codigo_municipio"] == "3550308"

    def test_calculo_iss_correto(self) -> None:
        empresa = self._empresa()
        payload = self._payload(valor="1000.00", aliquota="2.00")
        data = _construir_payload_focus(empresa, payload, "001")  # type: ignore[arg-type]

        assert Decimal(data["servico"]["valor_iss"]) == Decimal("20.00")
        assert Decimal(data["servico"]["base_calculo"]) == Decimal("1000.00")

    def test_calculo_iss_com_deducao(self) -> None:
        empresa = self._empresa()
        payload = self._payload(valor="1000.00", aliquota="2.00", deducoes="200.00")
        data = _construir_payload_focus(empresa, payload, "001")  # type: ignore[arg-type]

        # base = 1000 - 200 = 800; iss = 800 * 2% = 16
        assert Decimal(data["servico"]["base_calculo"]) == Decimal("800.00")
        assert Decimal(data["servico"]["valor_iss"]) == Decimal("16.00")

    def test_aliquota_maxima_5_porcento(self) -> None:
        payload = EmitirNfseIn(
            natureza_operacao=1,
            servico_descricao="Serviço qualquer",
            servico_codigo="01.07",
            servico_valor=Decimal("500.00"),
            aliquota_iss=Decimal("5.00"),
        )
        empresa = self._empresa()
        data = _construir_payload_focus(empresa, payload, "001")  # type: ignore[arg-type]
        assert Decimal(data["servico"]["valor_iss"]) == Decimal("25.00")

    def test_tomador_cnpj_incluido(self) -> None:
        payload = EmitirNfseIn(
            natureza_operacao=1,
            servico_descricao="Consultoria",
            servico_codigo="17.01",
            servico_valor=Decimal("3000.00"),
            aliquota_iss=Decimal("2.00"),
            cnpj_tomador="11222333000181",
            razao_social_tomador="Tomador LTDA",
        )
        empresa = self._empresa()
        data = _construir_payload_focus(empresa, payload, "001")  # type: ignore[arg-type]
        assert data["tomador"]["cnpj"] == "11222333000181"
        assert data["tomador"]["razao_social"] == "Tomador LTDA"


class TestEmitirNfseInValidacao:
    """Testes de validação de campos — LC 116/2003 e regras de negócio."""

    def _base_valido(self, **kwargs: object) -> dict[str, object]:
        base: dict[str, object] = {
            "natureza_operacao": 1,
            "servico_descricao": "Desenvolvimento de sistema fiscal",
            "servico_codigo": "01.07",
            "servico_valor": Decimal("500.00"),
            "aliquota_iss": Decimal("2.00"),
        }
        base.update(kwargs)
        return base

    def test_aliquota_iss_minima_valida(self) -> None:
        payload = EmitirNfseIn(**self._base_valido(aliquota_iss=Decimal("2.00")))  # type: ignore[arg-type]
        assert payload.aliquota_iss == Decimal("2.00")

    def test_aliquota_iss_abaixo_minimo_rejeitada(self) -> None:
        with pytest.raises(ValidationError, match="aliquota_iss"):
            EmitirNfseIn(**self._base_valido(aliquota_iss=Decimal("1.99")))  # type: ignore[arg-type]

    def test_aliquota_iss_zero_rejeitada(self) -> None:
        with pytest.raises(ValidationError, match="aliquota_iss"):
            EmitirNfseIn(**self._base_valido(aliquota_iss=Decimal("0")))  # type: ignore[arg-type]

    def test_aliquota_iss_acima_maximo_rejeitada(self) -> None:
        with pytest.raises(ValidationError, match="aliquota_iss"):
            EmitirNfseIn(**self._base_valido(aliquota_iss=Decimal("5.01")))  # type: ignore[arg-type]

    def test_cpf_tomador_valido_aceito(self) -> None:
        payload = EmitirNfseIn(**self._base_valido(cpf_tomador="52998224725"))  # type: ignore[arg-type]
        assert payload.cpf_tomador == "52998224725"

    def test_cpf_tomador_digito_errado_rejeitado(self) -> None:
        with pytest.raises(ValidationError, match="CPF do tomador inválido"):
            EmitirNfseIn(**self._base_valido(cpf_tomador="52998224726"))  # type: ignore[arg-type]

    def test_cpf_tomador_sequencia_uniforme_rejeitada(self) -> None:
        with pytest.raises(ValidationError):
            EmitirNfseIn(**self._base_valido(cpf_tomador="11111111111"))  # type: ignore[arg-type]

    def test_cpf_tomador_nulo_aceito(self) -> None:
        payload = EmitirNfseIn(**self._base_valido())  # type: ignore[arg-type]
        assert payload.cpf_tomador is None

    def test_natureza_operacao_isencao_rejeitada(self) -> None:
        # MIN-3 da auditoria: natureza 3-6 (isento/imune/exigibilidade suspensa)
        # requer módulo de compliance — restringido a {1, 2} no MVP.
        with pytest.raises(ValidationError, match="natureza_operacao"):
            EmitirNfseIn(**self._base_valido(natureza_operacao=3))  # type: ignore[arg-type]

    def test_natureza_operacao_acima_6_rejeitada(self) -> None:
        with pytest.raises(ValidationError, match="natureza_operacao"):
            EmitirNfseIn(**self._base_valido(natureza_operacao=6))  # type: ignore[arg-type]

    def test_natureza_operacao_1_aceita(self) -> None:
        payload = EmitirNfseIn(**self._base_valido(natureza_operacao=1))  # type: ignore[arg-type]
        assert payload.natureza_operacao == 1

    def test_natureza_operacao_2_aceita(self) -> None:
        payload = EmitirNfseIn(**self._base_valido(natureza_operacao=2))  # type: ignore[arg-type]
        assert payload.natureza_operacao == 2


class TestEmitirNfseOut:
    def test_aviso_iss_presente_por_padrao(self) -> None:
        out = EmitirNfseOut(
            focus_ref="ref-001",
            status="processando",
            mensagem="em processamento",
            aviso_iss="Confirme a alíquota com a prefeitura.",
        )
        assert out.aviso_iss is not None
        assert "alíquota" in out.aviso_iss.lower() or "prefeitura" in out.aviso_iss.lower()

    def test_aviso_iss_opcional(self) -> None:
        out = EmitirNfseOut(
            focus_ref="ref-001",
            status="autorizada",
            mensagem="ok",
        )
        assert out.aviso_iss is None
