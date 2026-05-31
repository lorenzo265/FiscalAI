---
tags: [api, openapi, documentação, público]
atualizado: 2026-05-31
---

# Guia — OpenAPI Pública

## Acessar a documentação

| URL | Formato | Descrição |
|---|---|---|
| `https://api.fiscalai.com.br/docs` | Swagger UI interativo | Explore e execute endpoints |
| `https://api.fiscalai.com.br/redoc` | ReDoc (read-only) | Documentação navegável |
| `https://api.fiscalai.com.br/openapi.json` | JSON bruto | Para importar no Postman/Insomnia |

## Autenticação

1. Criar conta: `POST /auth/register`
2. Obter token: `POST /auth/login` → `{"access_token": "<jwt>", "expires_in": 3600}`
3. Incluir em todas as chamadas: `Authorization: Bearer <jwt>`

Token expira em 60 minutos (configurável via `JWT_EXPIRE_MINUTES`).

## Rate Limiting

| Tipo de endpoint | Limite |
|---|---|
| Endpoints comuns | 1000 req/hora por tenant |
| Endpoints sensíveis (`/auth`, `/pgdas`, `/sped`, `/notas`, `/certidoes`) | 100 req/hora por tenant |

Headers de resposta: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
Em caso de bloqueio: HTTP 429 com `Retry-After` em segundos.

## Importar no Postman

1. Postman → Import → Link → `https://api.fiscalai.com.br/openapi.json`
2. Criar variável de ambiente `base_url = https://api.fiscalai.com.br`
3. Criar variável `token` e popular com o resultado de `/auth/login`
4. Usar `{{token}}` como Bearer em "Authorization" da collection

## Versionamento

A API está na versão `1.0.0` (estável, todos os 22 sprints completos).
Breaking changes serão sinalizados com nova versão major e deprecation notice de 90 dias.

Relacionado: [[onboarding-dev]] · [[runbooks/deploy-producao]]
