"""Golden tests para validação de CNPJ — barreira de merge conforme §8.4 do Plano.

Todos os CNPJs foram verificados manualmente pelo algoritmo oficial de dois
dígitos verificadores (Instrução Normativa RFB nº 748/2007).

Nota: validar_cnpj() extrai somente dígitos antes de validar.
CNPJs com máscara (pontos, barra, hífen) também são aceitos.
O endpoint EmpresaIn usa pattern=r'^\\d{14}$' para exigir dígitos puros.
"""

from __future__ import annotations

import pytest

from app.modules.empresa.cnpj import validar_cnpj, validar_cpf

# ── CNPJs válidos (14 dígitos puros) ─────────────────────────────────────────

VALIDOS = [
    "12345678000195",  # base computada — dígitos 9,5
    "11222333000181",  # base computada — dígitos 8,1
    "45997418000153",  # base computada — dígitos 5,3
    "00000000000191",  # Banco do Brasil (domínio público) — dígitos 9,1
    "33000167000101",  # Petrobras (domínio público) — dígitos 0,1
    "60746948000112",  # Bradesco (domínio público) — dígitos 1,2
]

# ── CNPJs válidos com máscara (a função extrai os dígitos) ───────────────────

VALIDOS_COM_MASCARA = [
    "12.345.678/0001-95",
    "11.222.333/0001-81",
]

# ── CNPJs inválidos — dígito verificador errado ───────────────────────────────

INVALIDOS_DIGITO = [
    "12345678000196",  # último dígito: 5 → 6
    "11222333000182",  # último dígito: 1 → 2
    "12345678000185",  # primeiro verificador: 9 → 8
    "00000000000192",  # último dígito: 1 → 2
    "33000167000100",  # último dígito: 1 → 0
]

# ── CNPJs inválidos — sequência uniforme ─────────────────────────────────────

INVALIDOS_SEQUENCIA = [
    "00000000000000",
    "11111111111111",
    "22222222222222",
    "55555555555555",
    "99999999999999",
]

# ── CNPJs inválidos — comprimento errado (após extração de dígitos) ──────────

INVALIDOS_COMPRIMENTO = [
    "1234567800019",    # 13 dígitos
    "123456780001950",  # 15 dígitos
    "",                 # vazio
    "1234567800019X",   # 13 dígitos após extrair (X não é dígito)
]


@pytest.mark.parametrize("cnpj", VALIDOS)
def test_cnpj_valido(cnpj: str) -> None:
    assert validar_cnpj(cnpj) is True, f"CNPJ {cnpj} deveria ser válido"


@pytest.mark.parametrize("cnpj", VALIDOS_COM_MASCARA)
def test_cnpj_com_mascara_aceito(cnpj: str) -> None:
    assert validar_cnpj(cnpj) is True, f"CNPJ mascarado {cnpj} deveria ser aceito"


@pytest.mark.parametrize("cnpj", INVALIDOS_DIGITO)
def test_cnpj_digito_verificador_errado(cnpj: str) -> None:
    assert validar_cnpj(cnpj) is False, f"CNPJ {cnpj} deveria falhar por dígito verificador"


@pytest.mark.parametrize("cnpj", INVALIDOS_SEQUENCIA)
def test_cnpj_sequencia_uniforme_rejeitada(cnpj: str) -> None:
    assert validar_cnpj(cnpj) is False, f"CNPJ {cnpj} deveria falhar por ser sequência uniforme"


@pytest.mark.parametrize("cnpj", INVALIDOS_COMPRIMENTO)
def test_cnpj_comprimento_invalido(cnpj: str) -> None:
    assert validar_cnpj(cnpj) is False, f"CNPJ {cnpj} deveria falhar por comprimento inválido"


# ── Testes CPF ────────────────────────────────────────────────────────────────

CPF_VALIDOS = [
    "52998224725",  # verificado manualmente pelo algoritmo RFB
    "11144477735",  # verificado manualmente pelo algoritmo RFB
    "12345678909",  # derivado: base 123456789, d1=0, d2=9
]

CPF_INVALIDOS_DIGITO = [
    "52998224726",  # último dígito trocado: 5 → 6
    "11144477736",  # último dígito trocado: 5 → 6
    "12345678908",  # último dígito trocado: 9 → 8
]

CPF_INVALIDOS_SEQUENCIA = [
    "00000000000",
    "11111111111",
    "99999999999",
]

CPF_INVALIDOS_COMPRIMENTO = [
    "1234567890",   # 10 dígitos
    "123456789091",  # 12 dígitos
    "",
]


@pytest.mark.parametrize("cpf", CPF_VALIDOS)
def test_cpf_valido(cpf: str) -> None:
    assert validar_cpf(cpf) is True, f"CPF {cpf} deveria ser válido"


@pytest.mark.parametrize("cpf", CPF_INVALIDOS_DIGITO)
def test_cpf_digito_verificador_errado(cpf: str) -> None:
    assert validar_cpf(cpf) is False, f"CPF {cpf} deveria falhar por dígito verificador"


@pytest.mark.parametrize("cpf", CPF_INVALIDOS_SEQUENCIA)
def test_cpf_sequencia_uniforme_rejeitada(cpf: str) -> None:
    assert validar_cpf(cpf) is False, f"CPF {cpf} deveria falhar por ser sequência uniforme"


@pytest.mark.parametrize("cpf", CPF_INVALIDOS_COMPRIMENTO)
def test_cpf_comprimento_invalido(cpf: str) -> None:
    assert validar_cpf(cpf) is False, f"CPF {cpf} deveria falhar por comprimento inválido"
