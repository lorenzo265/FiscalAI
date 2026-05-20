"""Declarações anuais SN — DEFIS e DASN-SIMEI (Sprint 6 PR3).

DEFIS:        Declaração de Informações Socioeconômicas e Fiscais.
              Obrigatória para todo SN, vencimento 31/março do ano seguinte.
              Consolidação anual a partir das 12 ApuracaoFiscal mensais +
              dados socioeconômicos (sócios, lucro contábil, despesas) que
              o usuário fornece no momento da geração.

DASN-SIMEI:   Versão simplificada para MEI, prazo até 31/maio.
              Apenas receita bruta anual + flag de empregado.

Geração:      funções puras em :mod:`gerar_defis` e :mod:`gerar_dasn_simei`.
Persistência: service grava ``declaracao_anual`` com `payload_json` imutável.
Transmissão:  via SerproClient.transmitir_defis / .transmitir_dasn_simei.
"""
