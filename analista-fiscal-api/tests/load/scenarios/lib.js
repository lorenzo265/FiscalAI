// Helpers compartilhados pelos scenarios k6 (Sprint 19 PR3).
//
// Carrega o JSON de fixtures emitido pelo seed sintético em
// `tests/load/.seed/empresas.json`. Distribuído via SharedArray (uma cópia
// em memória, compartilhada entre VUs — economiza GB em escala FULL).

import { SharedArray } from 'k6/data';

export const API_URL = __ENV.API_URL || 'http://api:8000';
export const FIXTURES_PATH = __ENV.FIXTURES_PATH || '/load/.seed/empresas.json';

// SharedArray callback roda 1 vez no init phase (não por VU).
export const empresas = new SharedArray('empresas', () => {
  const data = JSON.parse(open(FIXTURES_PATH));
  if (!data.empresas || data.empresas.length === 0) {
    throw new Error(
      `Fixtures vazias em ${FIXTURES_PATH}. ` +
      `Rode o seed antes: poetry run python -m scripts.seed.seed_1k_tenants --scale smoke`
    );
  }
  return data.empresas;
});

// Pega uma empresa aleatória da pool. Distribuição uniforme — VU não precisa
// saber qual, só precisa de uma válida com JWT.
export function empresaAleatoria() {
  return empresas[Math.floor(Math.random() * empresas.length)];
}

export function headersAuth(e) {
  return {
    'Authorization': `Bearer ${e.jwt}`,
    'Content-Type': 'application/json',
  };
}

// Mês de competência rotativo — evita conflito de UNIQUE quando o cenário
// gera mais requests que meses no calendário. Combina VU + iteração.
export function competenciaRotativa(__VU, __ITER, anoBase = 2026) {
  const offset = (__VU * 13 + __ITER) % 12;
  const mes = (offset % 12) + 1;
  return `${anoBase}-${String(mes).padStart(2, '0')}`;
}
