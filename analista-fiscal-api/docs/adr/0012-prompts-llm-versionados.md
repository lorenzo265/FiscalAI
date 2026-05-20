# ADR 0012 — Prompts LLM versionados em arquivo

## Status

accepted (2026-05-20)

## Contexto

Sprints 3–5 introduziram chamadas LLM (assistente, classificador de intenção, encaminhamento marketplace, extração estruturada). Cada caller monta seu prompt como string Python inline no service.

Problemas observados na auditoria (relatório Sprint 1–3, 2026-05-20):

1. Diff de prompt some no `git blame` da função — review de mudança de prompt vira review de função inteira.
2. Eval suite (`tests/eval/*.jsonl`) referencia "o prompt do assistente" sem fixar versão — uma edição silenciosa em produção pode regredir 30% da acurácia sem ninguém ver.
3. Prompt cache do Gemini (TTL 7d para `system_instruction`) precisa de chave estável. Strings construídas dinamicamente quebram a cache.
4. Princípio §8.5 (citação obrigatória) exige instruções específicas no system prompt — espalhá-las pela base é onde regressões acontecem.

## Decisão

Centralizar todo prompt LLM público em `app/shared/llm/prompts/`. Convenções:

- **Arquivo por prompt:** `<modulo>_<nome>_v<N>.md` — ex.: `assistente_resposta_v1.md`, `marketplace_classificacao_v1.md`.
- **Front-matter YAML opcional** com `provider_pref`, `temperature_default`, `cache_ttl_seconds`, `obriga_citacao`.
- **Carregador único:** `from app.shared.llm.prompts import get_prompt`. Retorna `PromptVersionado` (Pydantic frozen) com `texto: str`, `versao: str`, `path: Path`.
- **Bump explícito:** mudança que altera output → criar `_v2.md`, não editar `_v1`. Caller passa a usar `get_prompt("assistente_resposta_v2")`. v1 fica até CI mostrar acurácia equivalente.
- **Eval suite fixa a versão:** cada caso JSONL declara `prompt_version` que deve casar com o `get_prompt` do caller. Mismatch = falha de teste.

## Consequências

**Positivas:**

- `git log app/shared/llm/prompts/assistente_resposta_v1.md` é a história verdadeira do prompt.
- Cache key estável (path + mtime do arquivo) — hit rate Gemini sobe.
- Review de prompt fica focado: PR muda 1 arquivo `.md`, reviewer não precisa percorrer service.
- A/B com `v1` e `v2` coexistindo é trivial — Roll forward por feature flag.

**Negativas:**

- Caller precisa carregar o arquivo (1 chamada extra, cacheada em memória do processo).
- Migração dos prompts inline existentes (assistente, classificador de intent, encaminhamento) é gradual — esta PR move só o do assistente como referência. Os outros viram tarefa de housekeeping rastreada em `log_agente.md`.

**Reversibilidade:** alta. Helper é fino; voltar a string inline é só substituir `get_prompt("x").texto` pela literal.

## Alternativas consideradas

- **Prompts em Postgres (tabela `prompt_versionado`)** — permitiria hot reload sem deploy. Rejeitado no MVP: latência extra, complica testes locais, não tem ganho real até termos prompt engineering em escala.
- **LangChain `PromptTemplate`** — descartado pela política anti-LangChain (Plano §3.6).
- **Inline + `# version: vN` em comentário** — fraco; o comentário pode mentir e o eval não pega.

## Pendência rastreada

Após esta PR, os seguintes callers ainda têm prompt inline e devem ser migrados em PR de housekeeping:

- `app/modules/whatsapp/intent.py` (classificador de intenção)
- `app/modules/e_cac/classificador.py` (intimações)
- `app/modules/conciliacao/...` (sugestão de match) — quando virar LLM-driven na Sprint 11+
