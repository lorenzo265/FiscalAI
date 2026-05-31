// Cenário smoke — só hit em /healthz e /readyz.
//
// Útil para validar que o stack docker-compose subiu, que o k6 alcança
// a API, e como warm-up antes dos cenários pesados. Não exige fixtures.

import http from 'k6/http';
import { check } from 'k6';
import { API_URL } from './lib.js';

export const options = {
  vus: 5,
  duration: '15s',
  thresholds: {
    'http_req_duration{endpoint:healthz}': ['p(99)<100'],
    'http_req_duration{endpoint:readyz}': ['p(99)<500'],
    'http_req_failed': ['rate<0.01'],
  },
};

export default function () {
  const r1 = http.get(`${API_URL}/healthz`, { tags: { endpoint: 'healthz' } });
  check(r1, { 'healthz ok': (r) => r.status === 200 });

  const r2 = http.get(`${API_URL}/readyz`, { tags: { endpoint: 'readyz' } });
  check(r2, { 'readyz 200 ou 503': (r) => r.status === 200 || r.status === 503 });
}
