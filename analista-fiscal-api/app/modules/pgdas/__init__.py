"""Módulo de transmissão PGDAS-D (Sprint 6 PR2).

PGDAS-D é a declaração mensal do Simples Nacional. O backend já calcula o
valor do DAS na Sprint 2 (`apuracao_fiscal.tipo='das'`); este módulo é
responsável por transmitir a declaração ao Portal do Simples Nacional via
SERPRO Integra Contador (idServico ``TRANSDECLARACAO11``) — exigência §8.12
do Plano: cliente delega via termo assinado no onboarding.
"""
