from __future__ import annotations


def validar_cpf(cpf: str) -> bool:
    """Valida CPF pelo algoritmo oficial dos dois dígitos verificadores.

    Aceita 11 dígitos numéricos (sem máscara). Rejeita sequências com todos
    os dígitos iguais (ex: 00000000000).
    """
    digits = "".join(c for c in cpf if c.isdigit())

    if len(digits) != 11:
        return False

    if len(set(digits)) == 1:
        return False

    def _digito(d: str, pesos: list[int]) -> int:
        soma = sum(int(d[i]) * pesos[i] for i in range(len(pesos)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    pesos1 = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]

    return int(digits[9]) == _digito(digits, pesos1) and int(digits[10]) == _digito(digits, pesos2)


def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ pelo algoritmo oficial dos dois dígitos verificadores.

    Aceita 14 dígitos numéricos (sem máscara). Rejeita sequências com todos
    os dígitos iguais (ex: 00000000000000).
    """
    digits = "".join(c for c in cnpj if c.isdigit())

    if len(digits) != 14:
        return False

    if len(set(digits)) == 1:
        return False

    def _digito(d: str, pesos: list[int]) -> int:
        soma = sum(int(d[i]) * pesos[i] for i in range(len(pesos)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    return int(digits[12]) == _digito(digits, pesos1) and int(digits[13]) == _digito(digits, pesos2)
