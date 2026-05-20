# ADR 0013 — Celery: instalação opt-in, esqueleto sempre presente

## Status

accepted (2026-05-20)

## Contexto

O `PlanoBackend.md` §3.3 lista Celery 5.4+ como worker oficial. A Sprint 11 PR3 (2026-05-17) configurou o beat schedule completo e decorou 4 tasks com `@celery_app.task(name=...)`. Porém, o pacote `celery[redis]` **não está no `pyproject.toml`**.

Razões observadas:

1. Suite de testes roda 992 verde sem Celery instalado — o esqueleto define um stub `class _CeleryStub` que expõe `.task()` no-op quando o import real falha. Isso mantém pytest+mypy verdes em CI.
2. Worker real precisa de Redis broker rodando — instalação local pesada para devs que só tocam módulos de domínio.
3. Tasks atuais (sync_e_cac_empresa, sync_pluggy, depreciacao_mensal, provisao_mensal) ainda são stubs — implementação real depende de infraestrutura de storage (S3/GCS) e KMS para credenciais.

## Decisão

Manter Celery como dependência **opt-in** no MVP:

- `app/workers/celery_app.py` declara stub fallback quando `celery` não pode ser importado.
- Workers decorados com `@celery_app.task(name="...", acks_late=True, max_retries=3, queue="default")` funcionam tanto com Celery real quanto com stub.
- Beat schedule está totalmente declarado (cron strings + horários BR) — quando o pacote for instalado, ele encontra as tasks pelos nomes registrados.
- Ativação em produção: `poetry add celery[redis] && docker compose up worker beat` — sem mudança de código de aplicação.

Esta política vale até a Sprint 14 (Reforma Tributária) ou primeira contratação real de pagantes (Marco Fase 2 = 50 pagantes), o que vier primeiro. Aí passa a ser dependência principal.

## Consequências

**Positivas:**

- CI/dev mantém suite rápida (~7s para unit + eval) sem orquestrar Redis broker dentro do harness.
- Mudança para Celery real é uma linha em `pyproject.toml` — sem refator no app.
- Decorador `@celery_app.task` é a fonte da verdade tanto para stub quanto para real — não há divergência de API.

**Negativas:**

- Tasks definidas hoje (`sync_e_cac_empresa` etc.) têm corpo placeholder. Implementação real fica para o PR de produção.
- Risco de divergência: alguém adicionar uma task que use API do Celery não suportada pelo stub. Mitigação: review explícito de tasks novas + smoke test que executa `_CeleryStub.task()` em CI.

**Reversibilidade:** alta. O pacote real é drop-in.

## Alternativas consideradas

- **Adotar Celery real desde o início** — rejeitado: adiciona ~50MB de dependências + serviço extra no docker-compose para benefício zero enquanto as tasks são stubs.
- **APScheduler in-process** — rejeitado: não escala horizontalmente, perde tasks ao reiniciar a API.
- **Arq (asyncio-native)** — interessante mas o time já tem familiaridade com Celery e o ecossistema brasileiro de exemplos é forte. Reabrir se Celery virar gargalo.

## Pendência rastreada

- Implementar corpos reais das 4 tasks (rastreado em `log_agente.md` — pendência consciente #1).
- Definir e documentar runbook de deploy do worker/beat antes da Sprint 14.
- Verificar `app/workers/celery_app.py` quando atualizar para Celery 5.5+ que mudou `task_acks_late` para `acks_late` em alguns paths.
