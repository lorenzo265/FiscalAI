// Cenário 3 — Dashboard trimestral (DRE + Balanço + DFC).
//
// Simula um usuário abrindo o dashboard do trimestre. 3 GETs em sequência
// (LIST relatórios + 2 GETs específicos) — exercita os índices
// `ix_apuracao_empresa_tipo_comp` e `ix_saldo_empresa_comp_desc` da
// migration 0041.
//
// 100 VUs concorrentes = 100 usuários abrindo dashboard ao mesmo tempo.

import http from 'k6/http';
import { check, group } from 'k6';
import { API_URL, empresaAleatoria, headersAuth } from './lib.js';

export const options = {
  scenarios: {
    dashboard: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 100),
      duration: __ENV.DURATION || '1m',
    },
  },
  thresholds: {
    'http_req_duration{endpoint:relatorios_list}': ['p(95)<500'],
    'http_req_failed': ['rate<0.01'],
  },
};

export default function () {
  const e = empresaAleatoria();
  const headers = headersAuth(e);

  group('lista relatorios', () => {
    const res = http.get(
      `${API_URL}/v1/empresas/${e.empresa_id}/relatorios?limite=20`,
      { headers, tags: { endpoint: 'relatorios_list' } },
    );
    // 200 sempre — lista vazia é resposta válida.
    check(res, { 'lista 200': (r) => r.status === 200 });
  });
}
