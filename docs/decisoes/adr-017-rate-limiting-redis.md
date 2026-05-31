---
id: ADR-017
titulo: "Rate limiting por tenant — Redis INCR + EXPIRE"
status: aceito
data: 2026-05-31
autores: [equipe-backend]
tags: [segurança, rate-limit, redis, sprint-21]
---

# ADR-017 — Rate limiting por tenant via Redis INCR+EXPIRE (Sprint 21)

## Contexto

O §14.3 do Plano define limites de requisições por tenant:
- 1000 req/hora endpoints comuns
- 100 req/hora endpoints sensíveis (auth, PGDAS, SPED, notas, certidões)

Sem rate limiting, um tenant com bug de loop ou um atacante com JWT válido pode saturar o pool de Postgres (20 conexões).

## Decisão

**Algoritmo:** Fixed Window Counter com Redis INCR atômico.

```
Chave: rl:<tenant_id>:<unix_hora_alinhada>
INCR → contador
if contador == 1: EXPIRE 3600  (só na primeira req da janela)
if contador > limite: HTTP 429
```

**Por que Fixed Window e não Sliding Window?**
- Fixed Window: O(1), 1 INCR + eventual EXPIRE. Implementação sem Lua.
- Sliding Window: O(log N) com ZSET. Mais preciso na borda da janela (max burst = 2× limite na virada), mas complexidade desnecessária para o volume atual de PMEs.
- Token Bucket: requer estado de timestamp do último token, 2 ops atômicas via Lua. Overkill.

**Extração de tenant sem re-validação de assinatura:** O middleware extrai o `tid` do JWT decodificando base64 sem verificar HMAC. A validação real ocorre em `get_tenant_context`. Isso é correto porque:
- Rate limiting é best-effort (fail-open).
- Um atacante que falsificar `tid` apenas consome cota de outro tenant (auto-sabotagem, não escalada de privilégio).

**Fail-open:** Redis indisponível → requisição passa. Disponibilidade > rate limiting em caso de falha de infra.

## Alternativas rejeitadas

- **nginx `limit_req`:** rate limiting no nível de IP, não de tenant. Errado para multi-tenant onde múltiplos tenants compartilham IPs via NAT.
- **Middleware Python com contador em memória:** não funciona com múltiplos pods (cada réplica tem seu próprio contador).
- **Token bucket Redis via Lua:** mais preciso, mas 2-3× mais complexo para o volume atual.

## Consequências

- `RateLimitMiddleware` registrado em `app/main.py` via `add_middleware`.
- Headers RFC 6585 em todas as respostas: `X-RateLimit-Limit/Remaining/Reset`, `Retry-After` em 429.
- 26 golden tests cobrem: janela horária, chave Redis, limites por path, mock Redis (permitido/bloqueado/fail-open).
- Burst máximo na virada de janela: 2× o limite (Fixed Window trade-off documentado e aceito).

Relacionado: [[decisoes/adr-016-hardening-seguranca]] · [[principios/10-observabilidade]] · [[sprints/sprint-21-hardening]]
