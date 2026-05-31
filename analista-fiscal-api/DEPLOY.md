# 🚀 DEPLOY — Analista Fiscal API

Mapeamento operacional do que precisa estar configurado para rodar o sistema, em dev e em produção. Cada setting tem uma **decisão documentada** — não é tutorial de "como obter chave", é o porquê do default.

**Última atualização:** 2026-05-27 (pós-Sprint 19.5).
**Suite atual:** 1821 testes · mypy strict 0 erros · 334 arquivos.
**Migrations:** 43 (`alembic/versions/0001` → `0044`).

> Para o knowledge graph (Obsidian), ver `docs/deploy.md` no repo-pai.

---

## §0. TL;DR — gates "hard" mínimos

**Sem estes 5 itens, a API não aceita primeiro request com sucesso em prod:**

1. **Celery instalado** (`poetry add celery[redis]`) + processos `worker` + `beat` rodando. Sem isso, 18 tasks agendadas (sync e-CAC, digest WhatsApp, alertas tabelas tributárias, geração SPED anual) ficam paradas — o sistema só atende request síncrono.
2. **`JWT_SECRET` ≥ 32 bytes**, não o placeholder `TROCAR_EM_PRODUCAO_...`. Gerar com `openssl rand -hex 32`.
3. **`FOCUS_NFE_TOKEN` válido** + `FOCUS_NFE_SANDBOX=false`. Sandbox em prod emite NFS-e fake — multa para o cliente porque a Prefeitura nunca recebe o documento.
4. **`SERPRO_CONSUMER_KEY` + `SERPRO_CONSUMER_SECRET` + `SERPRO_SANDBOX=false`**. PGDAS-D + certidões CND/CRF dependem disso.
5. **`DATABASE_URL` apontando para Postgres real** (não `localhost`) + `alembic upgrade head` rodado **uma vez** + extensions `pgcrypto` + `vector` carregadas (vem do `init.sql`).

**Gates "soft"** (sistema sobe, feature off):

| Off por padrão | Efeito |
|---|---|
| Storage S3/GCS | PDFs ficam em `BYTEA` no Postgres (escala limitada em ~100 empresas) |
| Langfuse | Tracing LLM desligado — debugging mais lento, sem custo extra |
| Sentry | Erros não centralizados — logs estruturados ainda capturam |
| Template WhatsApp | Digest gera snapshot `status='preparado'` mas não envia |
| EFD beat mensal | Empresas LP/LR podem gerar EFD manualmente via POST |
| CRF/CNDT scraping | Endpoints retornam `processando` (skeleton) |

---

## §1. Estrutura de runtime

**3 processos:**

| Processo | Comando | Porta | Função |
|---|---|---|---|
| API | `uvicorn app.main:app --workers 4` | 8000 | Endpoint JWT-protected (também webhooks) |
| Celery worker | `celery -A app.workers.celery_app worker -Q default -l info` | — | Executa tasks agendadas + on-demand |
| Celery beat | `celery -A app.workers.celery_app beat -l info` | — | Trigger das 18 beat tasks |

**3 stores:**

| Store | Versão | Função | Notas |
|---|---|---|---|
| Postgres | 16 + pgvector + pgcrypto | Multi-tenant via RLS, JSONB, NUMERIC(14,2), TIMESTAMPTZ, BYTEA | Image `pgvector/pgvector:pg16` traz vector pre-built |
| Redis | 7.4 | Cache (SCD, OAuth tokens, BrasilAPI), broker Celery, webhook dedup, rate limit | Cache fail-open (Sprint 19 PR2) |
| Ollama (dev) ou Gemini (prod) | Gemma 3 4B / Flash | LLM | Routing dual — ver §2.3 |

---

## §2. Settings — agrupadas por categoria

Espelho de `app/config.py`. Para cada bloco: tabela `Setting | Default | Dev | Prod | Decisão`.

### §2.1. Ambiente

| Setting | Default | Dev | Prod | Decisão |
|---|---|---|---|---|
| `ENVIRONMENT` | `local` | `local` | `prod` | Em `prod` ativa `_fail_fast_em_prod()` que bloqueia `localhost` em `DATABASE_URL`/`REDIS_URL` |
| `LOG_LEVEL` | `INFO` | `INFO` | `INFO` ou `WARNING` | `WARNING` em load tests; `DEBUG` para diagnóstico local |

### §2.2. Banco + Cache

| Setting | Default | Decisão |
|---|---|---|
| `DATABASE_URL` | `...@localhost:5432/fiscal` | Docker-compose expõe Postgres em `5434` (mapeado de `5432`) — evita colisão com Postgres do host. Em prod usa porta padrão. |
| `REDIS_URL` | `redis://localhost:6379/0` | DB `/0` reservado pra cache + broker. Sem clustering — Redis 7.4 single-node atende escala MVP. |
| `DB_POOL_SIZE` | `20` | Default SQLAlchemy 5 estoura em 1k empresas concorrentes (Sprint 19 PR1) |
| `DB_MAX_OVERFLOW` | `30` | Conexões extra em pico. Total possível: 50 conexões/processo × 4 workers = 200 conexões. Postgres `max_connections=200` no `docker-compose.load.yml`. |
| `DB_POOL_TIMEOUT` | `30s` | Esperar conexão antes de levantar (preferível a 500 timeout em pico) |
| `DB_POOL_RECYCLE` | `1800s` | Recicla conexão ociosa após 30min — evita TCP timeout de NAT/firewall |
| `SLOW_QUERY_THRESHOLD_MS` | `500` | Log estruturado `db.slow_query` em todas as sessões (Sprint 19 PR1). Setar `0` ou negativo desliga listener. |

### §2.3. LLM (Ollama dev / Gemini prod)

**DECISÃO ARQUITETURAL — rota dual:**

| Cenário | Provider | Custo | Por quê |
|---|---|---|---|
| Dev local | `OLLAMA_GEMMA_3_4B` | Zero | Privacy total, sem chave externa, latência ~2s |
| Prod sem PII | `GEMINI_2_5_FLASH_LITE` (default) | $0.10/M in + $0.40/M out | Custo baixo pra perguntas simples |
| Prod sem PII (cálculo) | `GEMINI_2_5_FLASH` | $0.30/M + $2.50/M | Acionado quando service marca `complex=True` |
| Prod sem PII (contábil) | `GEMINI_2_5_PRO` | $1.25/M + $10.00/M | Só quando explícito — escasso por custo |
| Prod com PII | `OLLAMA_GEMMA_3_4B` | Zero | `LLMRequest.contem_pii=True` **força** Ollama mesmo em prod (§7 LGPD) |
| Prod **sem `GEMINI_API_KEY`** | Fallback Ollama | Zero | Degradação graceful — sistema sobe, latência sobe, custo zero |

| Setting | Default | Decisão |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Em prod: URL interna do cluster Ollama (gateway sidecar) |
| `GEMINI_API_KEY` | `""` | Vazio = sem Gemini. Em dev é o default. Em prod precisa de chave real ou fallback Ollama. |
| `LANGFUSE_HOST` | `""` | Tracing LLM desligado por default. Ativa quando self-hosted BR está no ar (Sprint 21 hardening) |
| `LANGFUSE_PUBLIC_KEY` | `""` | Idem |
| `LANGFUSE_SECRET_KEY` | `""` | Idem |

### §2.4. JWT

| Setting | Default | Decisão |
|---|---|---|
| `JWT_SECRET` | `TROCAR_EM_PRODUCAO_gere_com_openssl_rand_hex_32` | Placeholder explícito força override consciente. Sem validação de tamanho hoje — **pendência: adicionar `assert len ≥ 32` em `_fail_fast_em_prod()`** |
| `JWT_ALGORITHM` | `HS256` | HMAC simples cabe em monorepo. RS256 reservado para Sprint 13+ quando marketplace exigir rotação de chaves sem reencrypt de tokens emitidos |
| `JWT_EXPIRE_MINUTES` | `60` | Access token de 1h. Refresh token não implementado — usuário re-loga após expirar |

### §2.5. Focus NFe

| Setting | Default | Decisão |
|---|---|---|
| `FOCUS_NFE_TOKEN` | `""` | Token de produção difere do sandbox. Sem token: emissão NFS-e cai em 401 |
| `FOCUS_NFE_SANDBOX` | `true` | **Crítico: SANDBOX=true em prod emite NFS-e fake.** Default `true` protege dev de emitir acidentalmente. Flip explícito em prod |
| `FOCUS_NFSE_ENVIA_CBS_IBS` | `false` | Sprint 14 PR2 — espera Focus documentar API para >7 prefeituras ADN (pendência #19) |

### §2.6. Meta WhatsApp

| Setting | Default | Decisão |
|---|---|---|
| `META_WHATSAPP_TOKEN` | `""` | Bearer token do Meta Graph API |
| `META_WHATSAPP_PHONE_ID` | `""` | ID do número WhatsApp Business |
| `META_WHATSAPP_APP_SECRET` | `""` | App secret para HMAC-SHA256 do webhook. Vazio = webhook rejeita tudo (fail-closed) |
| `META_WHATSAPP_VERIFY_TOKEN` | `fiscalai-webhook-verify` | String fixa que coincide com o painel Meta no momento do verify |
| `WHATSAPP_DIGEST_TEMPLATE_NAME` | `weekly_digest_pt_br` | Nome do template UTILITY aprovado no Meta |
| `WHATSAPP_DIGEST_LANG_CODE` | `pt_BR` | BCP-47 com underscore |
| `WHATSAPP_DIGEST_TEMPLATE_ATIVO` | `false` | Flag opt-in para envio real. False = digest fica em `status='preparado'` sem enviar (Sprint 15.5) |

### §2.7. BrasilAPI

| Setting | Default | Decisão |
|---|---|---|
| `BRASIL_API_URL` | `https://brasilapi.com.br` | Pública, sem auth. Cache Redis 30 dias evita rate limit |

### §2.8. SERPRO Integra Contador

| Setting | Default | Decisão |
|---|---|---|
| `SERPRO_BASE_URL` | `https://apigateway.serpro.gov.br` | Único endpoint (sandbox vs prod controlado por `SANDBOX` flag + path) |
| `SERPRO_CONSUMER_KEY` | `""` | Plano contratado no Loja SERPRO (cota mensal) |
| `SERPRO_CONSUMER_SECRET` | `""` | Idem |
| `SERPRO_SANDBOX` | `true` | Default `true` em dev pra não consumir cota mensal real |
| `SERPRO_OAUTH_TTL_MARGIN_SEC` | `60` | Margem para renovar token antes de expirar |
| `SERPRO_CERT_ENCRYPTION_KEY` | `""` | Base64 32 bytes que envelopa o e-CNPJ (.p12) do cliente em pgcrypto. **Em prod vem de KMS**, não de envvar direto |

### §2.9. Pluggy Open Finance

| Setting | Default | Decisão |
|---|---|---|
| `PLUGGY_BASE_URL` | `https://api.pluggy.ai` | Único endpoint |
| `PLUGGY_CLIENT_ID` | `""` | Gerado no painel pluggy.ai |
| `PLUGGY_CLIENT_SECRET` | `""` | Idem |
| `PLUGGY_WEBHOOK_SECRET` | `""` | HMAC-SHA256 do webhook. **Vazio = HMAC valida com string vazia = rejeita tudo** (fail-closed) |
| `PLUGGY_CONNECT_TOKEN_TTL_MIN` | `30` | TTL do connect_token que vai pro widget |
| `PLUGGY_API_KEY_TTL_MARGIN_SEC` | `120` | Margem da API key (2h TTL na Pluggy) |

### §2.10. Admin tokens

| Setting | Default | Decisão |
|---|---|---|
| `MARKETPLACE_ADMIN_TOKEN` | `""` | Vazio = `/v1/admin/*` retornam 503 (Sprint 13 PR1). Mesmo token cobre `/v1/admin/tabelas/*` da Sprint 19.5 |
| `ADMIN_WHATSAPP_PHONE` | `None` | Opcional. Quando configurado, digest semanal inclui bullets de alertas críticos do painel admin (Sprint 19.5 PR2) |

---

## §3. Integrações externas — estado por cliente

| Cliente | Arquivo | Settings críticas | Estado | Modo prod |
|---|---|---|---|---|
| Focus NFe | `app/shared/integrations/focus_nfe/client.py` | `FOCUS_NFE_TOKEN` + `SANDBOX` | ✅ completo, sandbox por default | Token ativo + `SANDBOX=false` |
| SERPRO | `app/shared/integrations/serpro/client.py` | `KEY`+`SECRET`+`CERT_ENC_KEY` | ✅ OAuth + cert A1 encriptado | Keys ativas + `SANDBOX=false` |
| Pluggy | `app/shared/integrations/pluggy/client.py` | `CLIENT_ID`+`SECRET`+`WEBHOOK_SECRET` | ✅ completo | Keys + webhook + worker admin (depende #4) |
| Meta WhatsApp | `app/shared/integrations/meta_whatsapp/sender.py` | `TOKEN`+`PHONE_ID`+`APP_SECRET`+`VERIFY_TOKEN` | ✅ completo, template inativo | Template aprovado + `WHATSAPP_DIGEST_TEMPLATE_ATIVO=true` |
| BrasilAPI | `app/shared/integrations/brasil_api/client.py` | (sem chave) | ✅ público | Manter cache Redis ativo |
| DOU | `app/shared/integrations/dou/client.py` | (sem chave) | ✅ cliente fail-soft | Worker `tabelas.varrer_dou_mensal` real (pendência #41) |

Todos os clientes têm: `tenacity` retry com `wait_exponential_jitter(initial=1, max=8|10)`, timeout explícito, `idempotency_key` em POST, log estruturado.

---

## §4. Celery — 18 beat tasks

Definidas em `app/workers/celery_app.py::_beat_schedule()`. **Hoje todas têm corpo skeleton** (`return {"status": "noop"}` ou similar) — shipping the schedule + skeleton habilita o gate "beat funcionando". Corpos reais entram em PRs específicos quando feature precisar.

| Task | Cron | Sprint | Corpo |
|---|---|---|---|
| `e_cac.sync_empresa` | 06:00 diário | 6 PR3 | stub |
| `open_finance.sync_pluggy_empresa` | 07:00 diário | 7 PR2 | stub |
| `imobilizado.gerar_depreciacao_empresa` | dia 1/mês 03:00 | 8 PR1 | stub |
| `provisoes.gerar_provisao_empresa` | dia 28/mês 23:00 | 8 PR2 | stub |
| `rbt12.refresh_mensal` | dia 2/mês 06:00 | 9 PR2 | ✅ real |
| `whatsapp.expurgar_processadas` | 04:00 diário | Fase 2 PR7 | ✅ real |
| `marketplace.expirar_sla` | de hora em hora | 13 PR3 | ✅ real |
| `marketplace.recalcular_rating` | 02:00 diário | 13 PR3 | ✅ real |
| `marketplace.expurgar_pii` | 03:00 diário | 13 PR3 | ✅ real |
| `marketplace.check_crc_mensal` | dia 5/mês 06:00 | 13 PR3 | stub |
| `reforma.refresh_cbs_ibs_historico` | 04:30 diário | 14 PR3 | ✅ real |
| `advisor.detectar_anomalias_diario` | 07:30 diário | 15 PR1 | ✅ real |
| `advisor.gerar_digest_semanal` | seg 06:00 | 15 PR3 | ✅ real |
| `advisor.enviar_digests_preparados` | seg 06:30 | 15.5 PR3 | ✅ real (gating por `WHATSAPP_DIGEST_TEMPLATE_ATIVO`) |
| `sped.gerar_ecd_anual` | 03/abril 04:00 | 16 PR3 | ✅ real |
| `sped.gerar_ecf_anual` | 03/junho 04:00 | 16 PR3 | ✅ real |
| `tabelas.verificar_vigencias` | 06:15 diário | 19.5 PR2 | ✅ real |
| `tabelas.varrer_dou_mensal` | dia 5/mês 04:00 | 19.5 PR3 | ⚠️ stub do pipeline DOU+LLM (pendência #41) |

**Instalação:** Celery não está em `pyproject.toml` por default — é opt-in (pendência #1):

```powershell
poetry add celery[redis]
poetry run celery -A app.workers.celery_app worker -Q default -l info
poetry run celery -A app.workers.celery_app beat -l info
```

Cada worker usa `app/shared/db/perf.py::build_async_engine` (Sprint 19 PR1) e roda `SET LOCAL ROLE` apropriado conforme o caso (`fiscal_app` para tenant-scoped, `tax_table_admin` para painel admin cross-tenant).

---

## §5. Storage de arquivos (S3/GCS)

**Estado atual: 100% BYTEA.** Blobs grandes em `arquivo_sped.conteudo_bytea`, `documento_fiscal.xml_bytea`, recibos SERPRO em coluna. Funciona até ~100 empresas; depois disso vai ficar pesado.

**Módulos canônicos que persistem blob:**

| Módulo | Tipo | Coluna |
|---|---|---|
| SERPRO audit | Recibo PGDAS/DEFIS/Certidão | `serpro_audit.payload_jsonb` (text) + `storage_key` (NULL) |
| Focus NFe | DANFSE (PDF/XML) | `documento_fiscal.xml_bytea` |
| Pessoal | Holerite PDF | `storage_key` (NULL — pendência #11) |
| SPED | ECD/ECF/EFD anuais | `arquivo_sped.conteudo_bytea` |

**Decisão:** aceito até piloto pagar começar. S3 entra em PR dedicado pré-Sprint 20 (pendência #2). Schema do `storage_key` já está pronto — só precisa do client + migration de backfill.

---

## §6. Observabilidade

| Stack | Setting | Estado | Decisão |
|---|---|---|---|
| Slow query log | `SLOW_QUERY_THRESHOLD_MS=500` | ✅ ativo | structlog `db.slow_query` em todas as sessões (Sprint 19 PR1). Default 500ms cobre 95% de queries |
| Langfuse (LLM tracing) | `LANGFUSE_HOST/PUBLIC/SECRET` | ⚠️ off por default | Ativa quando stack self-hosted BR estiver no ar |
| Sentry (errors) | (sem setting hoje) | ❌ não plugado | Adicionar `SENTRY_DSN` em `app/config.py` + init em `app/main.py` no PR de hardening |
| Prometheus (`/metrics`) | (sem setting) | ❌ rota ausente | Adicionar via `prometheus-fastapi-instrumentator` em PR de hardening |
| Grafana + Tempo + Loki | (sem infra) | ❌ stack BR não montado | Sprint 21 hardening |

**Healthchecks** em `app/main.py:203-241`:
- `/healthz` — liveness, sempre 200 enquanto processo vivo
- `/readyz` — readiness, checa Postgres + Redis acessíveis; 503 se algum down

---

## §7. LGPD + Segurança

**Estado consolidado:**

| Item | Estado | Decisão |
|---|---|---|
| AES-256 (pgcrypto) | ⚠️ parcial | Chave em `SERPRO_CERT_ENCRYPTION_KEY` para e-CNPJ. Outros campos sensíveis (CPF sócio, cert eSocial) ficam para Sprint 21 |
| pgcrypto extension | ✅ ativo | `CREATE EXTENSION pgcrypto` em `infra/postgres/init.sql` |
| pgvector | ✅ ativo | Image `pgvector/pgvector:pg16` traz pre-built |
| Cert A1 (.pfx/.p12) | ⚠️ encriptado em DB | Coluna Postgres + pgcrypto + chave KMS-derived. Vault opcional na Sprint 21 |
| JWT secret comprimento | ❌ não validado | **Pendência: assert `len(JWT_SECRET) >= 32` em `_fail_fast_em_prod()`** |
| RLS multi-tenant | ✅ ativo | `SET LOCAL app.tenant_id` em `get_session` (`app/shared/db/deps.py`) |
| Role `fiscal_app` (não-superuser) | ✅ ativo | `init.sql` cria role + grants. Superuser bypassa RLS — não usamos no app |
| Role `tax_table_admin` | ✅ ativo (Sprint 19.5) | `REVOKE UPDATE, DELETE FROM PUBLIC` em 8 tabelas SCD + log audit |
| Role `marketplace_partner` | ✅ ativo (Sprint 13 PR3) | Policy `consulta_mkt_parceiro` com GUC `app.contador_id` |

---

## §8. Bootstrap local — 6 comandos

```powershell
# 0. PATH (Device Guard bloqueia poetry.exe direto na máquina do dev)
$env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"

# 1. Instalar dependências
poetry install --no-root --with dev

# 2. Subir Postgres + Redis + Ollama
docker compose up -d

# 3. Rodar migrations (43 hoje)
poetry run alembic upgrade head

# 4. Pull do modelo Gemma 3 4B no Ollama (~3GB, opcional se rota cloud)
docker exec fiscal_ollama ollama pull gemma3:4b

# 5. Validar setup
poetry run python -m pytest tests/unit tests/eval -q

# 6. Servir API local (reload em mudanças)
poetry run uvicorn app.main:app --reload
```

Após esses 6 passos, `curl http://localhost:8000/healthz` retorna `{"status":"ok"}`.

**Validar settings carregam:**

```powershell
poetry run python -c "from app.config import get_settings; print(get_settings())"
```

---

## §9. Deploy produção — sequência

> Helm/Terraform ainda não implementados (`infra/k8s/`, `infra/terraform/` são placeholders). Esta seção descreve a sequência manual; quando IaC entrar, basta empacotar.

1. **Provisionar infra:**
   - Postgres 16 com extensions: `pgvector`, `pgcrypto`, `pg_stat_statements` (Sprint 19 PR1)
   - Redis 7.4 single-node
   - KMS para encryption keys (AWS KMS, GCP KMS, ou Vault)
   - S3/GCS bucket para PDFs (quando #2 sair)
   - Secret manager (AWS Secrets Manager / Vault) para tokens

2. **Build images:**
   ```bash
   docker build -f infra/docker/Dockerfile.api    -t fiscal-api:$TAG    .
   docker build -f infra/docker/Dockerfile.worker -t fiscal-worker:$TAG .
   docker build -f infra/docker/Dockerfile.beat   -t fiscal-beat:$TAG   .
   ```

3. **Carregar segredos:**
   - Sincronizar `.env` (ou ConfigMap + Secret) com valores reais
   - `SERPRO_CERT_ENCRYPTION_KEY` vem de KMS — não de envvar direto

4. **Rodar migrations** (1× via job/init container):
   ```bash
   poetry run alembic upgrade head
   ```

5. **Seeds** (ver §10):
   - Tabelas SCD tributárias INSS/IRRF/FGTS 2026 → `POST /v1/admin/tabelas/<tipo>/vigencia` (Sprint 19.5)
   - Seleic mensal → atualização BCB (futuro)

6. **Health verification:**
   - `GET /healthz` deve retornar 200
   - `GET /readyz` deve retornar 200 (Postgres + Redis OK)
   - Smoke test: registrar tenant + criar empresa + apurar DAS

---

## §10. Seeds obrigatórios

Migrations específicas que seedaram dados em produção. Tabelas SCD podem (e devem) ser atualizadas via API admin, não por nova migration.

| Tabela | Migration que seedou | Como atualizar em prod |
|---|---|---|
| `tabela_inss_faixa` | `0016` (Sprint 10) — só 2025 | `POST /v1/admin/tabelas/inss/vigencia` (Sprint 19.5) |
| `tabela_irrf_faixa` | `0016` (Sprint 10) — só 2025 | `POST /v1/admin/tabelas/irrf/vigencia` |
| `tabela_fgts_aliquota` | `0016` (Sprint 10) | `POST /v1/admin/tabelas/fgts/vigencia` |
| `tabela_simples_faixa` | `0002` (Sprint 2) — 5 anexos | `POST /v1/admin/tabelas/simples-nacional/vigencia` |
| `presuncao_lucro_presumido` | Sprint 11 PR1 | `POST /v1/admin/tabelas/presuncao-lp/vigencia` |
| `aliquota_icms_uf` | Sprint 11 PR2 — 27 UFs | `POST /v1/admin/tabelas/icms-uf/vigencia` |
| `aliquota_cbs_ibs` | Sprint 14 PR1 — fase teste 2026 | `POST /v1/admin/tabelas/cbs-ibs/vigencia` |
| `selic_mensal` | Sprint 4 + atualização manual | Script BCB SGS mensal (futuro) |
| `conta_referencial_rfb` | Sprint 9 PR1 — 3500+ contas | Estável, sem atualização recorrente |

**Decisão arquitetural (Sprint 19.5):** atualização de tabela tributária = **POST via API admin**, não migration nova. O trigger SCD `scd_close_previous_valid_to` (migration 0025) fecha `valid_to` da vigência anterior automaticamente.

---

## §11. Pendências `[risco-deploy]` — referência cruzada

Lista consolidada das 10 pendências `[risco-deploy]` do `log_agente.md` §"Pendências conscientes":

| # | Pendência | Sprint endereçará | Esforço |
|---|---|---|---|
| **1** | Celery instalado real (workers + beat ativos) | Sprint 20 PR4 housekeeping | 2d |
| **2** | Storage S3/GCS de PDFs | PR pré-Sprint 20 | 2d |
| **4** | Webhook Pluggy → sync inline (depende #1) | Sprint 20 PR4 | 1d |
| **11** | Holerite PDF (depende #2) | Sprint 20 PR4 | 1d |
| **17** | `codigo_municipio_ibge` NOT NULL antes da janela fechar | PR pré-Sprint 20 | 0.5d |
| **18** | WhatsApp dedup 7d validação Grafana (depende #1) | Sprint 20 PR4 | passivo |
| **34** | EFD beat schedule mensal (depende #1) | Sprint 20 PR4 | 0.5d |
| **40** | Importador SPED workers >50MB (depende #1) | Sprint 20 PR4 | 1d |
| **41** ⭐ | Wiring live worker DOU + LLM real | Sprint 20 PR4 | 1d |
| **42** ⭐ | Hook digest admin plugado no `gera_digest_semanal.py` | Sprint 20 PR4 | 0.5d |

**Total: ~10 dias = 1 sprint dedicada de housekeeping pré-piloto.**

⭐ = pendências introduzidas pela Sprint 19.5 PR3.

---

## Histórico

- **2026-05-27** — documento criado pós-Sprint 19.5 (1821 testes, 334 arquivos).

## Relacionado

- `docs/deploy.md` (entrada Obsidian no knowledge graph)
- `log_agente.md` §"Pendências conscientes" — 43 itens com tags de severidade
- `docs/PlanoBackend.md` §11 — cronograma de sprints
- `docs/roadmap.md` — estado atual (21 sprints concluídas)
