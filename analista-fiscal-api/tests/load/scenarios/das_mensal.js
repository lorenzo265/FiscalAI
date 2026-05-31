// Cenário 1 — DAS mensal Simples Nacional em paralelo.
//
// Hit POST /v1/empresas/{empresa_id}/apuracoes/das com competência rotativa.
// Mede latência de cálculo + persistência de uma apuração que envolve:
//   * RBT12 lookup na MV `rbt12_mensal` (Sprint 14 PR3)
//   * Faixa SCD lookup em `faixa_simples`
//   * INSERT em `apuracao_fiscal`
//
// Roda contra dataset seedado (qualquer escala). Use `scale=full` para
// alvo do plano (1k empresas paralelo).
//
// Execução:
//   k6 run -e API_URL=http://api:8000 scenarios/das_mensal.js
//
// Thresholds (PlanoBackend §11.1 Fase 3 + ajustes Sprint 19):
//   * p99 < 1s (target inicial — Sprint 20 quer p99 < 500ms para LP)
//   * erro 5xx < 0.5%
//   * checks > 99%

import http from 'k6/http';
import { check } from 'k6';
import {
  API_URL,
  competenciaRotativa,
  empresaAleatoria,
  headersAuth,
} from './lib.js';

export const options = {
  scenarios: {
    das_constante: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.RATE || 20),       // req/s alvo
      timeUnit: '1s',
      duration: __ENV.DURATION || '1m',
      preAllocatedVUs: Number(__ENV.PRE_VUS || 50),
      maxVUs: Number(__ENV.MAX_VUS || 200),
    },
  },
  thresholds: {
    'http_req_duration{endpoint:das}': ['p(99)<1000'],
    'http_req_failed{endpoint:das}': ['rate<0.005'],
    'checks{endpoint:das}': ['rate>0.99'],
  },
};

export default function () {
  const e = empresaAleatoria();
  const payload = JSON.stringify({
    competencia: competenciaRotativa(__VU, __ITER),
    // Valor pequeno para garantir que cai na faixa configurada pelo seed
    // (RBT12 ~ R$ 600k → faixa 3 do Anexo I).
    receita_mes: '15000.00',
  });
  const res = http.post(
    `${API_URL}/v1/empresas/${e.empresa_id}/apuracoes/das`,
    payload,
    { headers: headersAuth(e), tags: { endpoint: 'das' } },
  );
  // 201 = criada agora. 409 (ApuracaoJaExiste) é OK em re-run com
  // mesma competência — não é "falha" do ponto de vista de perf.
  check(res, {
    'das ok ou ja-existe': (r) => r.status === 201 || r.status === 409,
  }, { endpoint: 'das' });
}
