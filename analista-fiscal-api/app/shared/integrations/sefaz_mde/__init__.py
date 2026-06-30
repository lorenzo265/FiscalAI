"""Integração com os webservices MD-e da SEFAZ:
DistribuiçãoDFe (NFeDistribuicaoDFe) + RecepcaoEvento.

PR2 → DistribuiçãoDFe (baixar documentos por NSU).
PR3 → RecepcaoEvento (transmitir evento de manifestação).

Expõe:
  * ``SefazMdeProvider`` — Protocol (contrato de injeção de dependência).
  * ``_FakeSefazMdeProvider`` — provider determinístico para dev/CI (sem rede).
  * ``FocusSefazMdeProvider`` — provider real via Focus NFe REST (best-effort).
  * ``build_sefaz_mde_provider`` — factory que escolhe o provider baseado em settings.
  * DTOs: ``ResultadoDistribuicao``, ``ResumoNFeDestinada``, ``ResultadoTransmissaoEvento``.
  * ``CSTAT_ACEITOS_MDE`` — frozenset{135, 136} (NT 2014.002 §6.1).

[follow-up PR3] Confirmar endpoints Focus NFe para DistribuiçãoDFe e RecepcaoEvento
antes de ligar em produção. A Focus NFe pode não ter wrappers REST para esses
webservices SOAP e exigir integração direta com o SEFAZ AN.
"""
