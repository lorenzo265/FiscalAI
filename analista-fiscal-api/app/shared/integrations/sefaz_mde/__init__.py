"""Integração com o serviço DistribuiçãoDFe (NFeDistribuicaoDFe) da SEFAZ.

PR2 do módulo de Manifestação do Destinatário (MD-e).

Expõe:
  * ``SefazMdeProvider`` — Protocol (contrato de injeção de dependência).
  * ``_FakeSefazMdeProvider`` — provider determinístico para dev/CI (sem rede).
  * ``FocusSefazMdeProvider`` — provider real via Focus NFe REST (best-effort).
  * ``build_sefaz_mde_provider`` — factory que escolhe o provider baseado em settings.
  * ``ResultadoDistribuicao``, ``ResumoNFeDestinada`` — DTOs de retorno.

Transmissão de evento (RecepcaoEvento) fica para PR3.
"""
