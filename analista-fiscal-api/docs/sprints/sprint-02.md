# Sprint 2 — Ingestão XML NF-e + DAS Simples Nacional

**Tema:** Parser `nfelib`/defusedxml, ingestão upload + IMAP skeleton. Calculadora DAS com 5 anexos + Fator R + RBT12. Golden tests bloqueando merge.

**Início:** 2026-05-11
**Critério de fechamento:** todos os marcos abaixo ✅. **Golden tests DAS + parser NF-e bloqueando merge.**

> Fonte literal: `PlanoBackend.md` §9 — "Parser nfelib, ingestão upload + IMAP, calculadora DAS SN com 5 anexos + Fator R + RBT12, golden tests bloqueando merge."

## Marcos binários

- [x] `app/modules/fiscal/calcula_das.py` — `FaixaDAS`, `ResultadoDAS`, `calcular_das()` puro, `resolver_anexo_fator_r()` — zero I/O
- [x] `app/modules/ingestao/parser.py` — `parse_xml_nfe()` puro via defusedxml (Clark notation), extrai 16 campos do NF-e 4.0
- [x] `app/shared/db/models.py` atualizado — `DocumentoFiscal`, `TabelaSimplesFaixa`, `ApuracaoFiscal` + relationships em `Empresa`
- [x] `app/shared/exceptions.py` atualizado — `XmlInvalido`, `DocumentoJaIngerido`, `TabelaTributariaAusente`, `ApuracaoJaExiste`, `RegimeIncompativel`, `FatorRObrigatorio`
- [x] `app/modules/fiscal/schemas.py` — `ApuracaoDASIn`, `ApuracaoDASOut`, `ApuracaoListOut`
- [x] `app/modules/ingestao/schemas.py` — `DocumentoFiscalOut`, `IngestaoResultadoOut`
- [x] `app/modules/fiscal/repo.py` — `TabelaSimplesRepo.faixas_vigentes()`, `ApuracaoFiscalRepo`
- [x] `app/modules/ingestao/repo.py` — `DocumentoFiscalRepo.buscar_por_chave()`, `listar_empresa()`
- [x] `app/modules/fiscal/service.py` — `FiscalService.calcular_e_salvar_das()` com resolução de Fator R
- [x] `app/modules/ingestao/service.py` — `IngestaoService.ingerir_upload()` com idempotência por chave
- [x] `app/modules/fiscal/router.py` — `POST /v1/empresas/{id}/apuracoes/das`, `GET /v1/empresas/{id}/apuracoes/{comp}/das`
- [x] `app/modules/ingestao/router.py` — `POST /v1/empresas/{id}/ingestao/upload`, `GET /v1/empresas/{id}/documentos`
- [x] `app/workers/tasks/ingestao_imap.py` — skeleton Celery `sync_imap_empresa` (implementação: Sprint 3)
- [x] `alembic/versions/0002_sprint2_ingestao_fiscal.py` — `documento_fiscal` + `tabela_simples_faixa` + `apuracao_fiscal` + RLS + seed 30 faixas CGSN 140/2018
- [x] `tests/golden/simples_nacional/*.json` — 8 golden cases cobrindo todos os ramos (I/II/III/IV/V, Fator R, RBT12=0, teto SN)
- [x] `tests/unit/fiscal/test_calcula_das.py` — 18 testes (8 golden parametrizados + testes erro + Fator R)
- [x] `tests/unit/ingestao/test_parser_nfe.py` — 6 testes parser (válido, NFC-e, malformado, sem infNFe, timezone, fallback chave)
- [x] `pyproject.toml` atualizado — `defusedxml`, `python-multipart`
- [x] `app/main.py` atualizado — routers `fiscal` e `ingestao` incluídos
- [x] **63 testes passando, 0 regressões do Sprint 1**
- [ ] **Validação manual:** `docker compose up -d && poetry run alembic upgrade head` → 30 faixas seed OK
- [ ] **Validação manual:** `POST /v1/empresas/{id}/ingestao/upload` com XML real → 201 + DocumentoFiscalOut
- [ ] **Validação manual:** `POST /v1/empresas/{id}/apuracoes/das` com competencia=2026-05 → 201 + valor correto
- [ ] **Validação manual:** `poetry run pytest` → todos passando
- [ ] **Validação manual:** `poetry run mypy app` → sem erros

## Decisões de design (fora do Plano, documentadas aqui)

| Decisão | Escolha | Justificativa |
|---|---|---|
| Parser XML | defusedxml + Clark notation | nfelib (binding xsdata) tem API instável entre versões; defusedxml é estável, seguro (previne XXE), stdlib-like |
| `calcular_das` recebe `faixas` como parâmetro | Pure function — nenhuma dependência de I/O | Permite golden tests sem banco; tabelas vêm do banco no service layer |
| Resolução Fator R | Separada em `resolver_anexo_fator_r()` | Testável isoladamente; service faz a resolução antes de buscar faixas |
| Idempotência upload | Checagem por chave NF-e antes de persistir | Evita duplicata sem precisar de `idempotency_key` no header (a chave já é o idempotency key natural) |
| `ApuracaoFiscal.output_jsonb` | JSONB livre com `valor_das`, `aliquota_efetiva` etc. | Evita schema migration a cada mudança de cálculo; golden tests validam o valor, não o schema JSONB |
| IMAP | Skeleton apenas | Requer configuração de servidor IMAP por empresa (Sprint 3: UI + config store) |
| `python-multipart` | Adicionado ao pyproject.toml | FastAPI exige para `UploadFile` |

## Fora de escopo (rejeitar até Sprint 3+)

- ❌ IMAP real (imaplib2, auth OAuth IMAP) — Sprint 3
- ❌ NFS-e ADN nacional — Sprint 3 (schema diferente do NF-e)
- ❌ CT-e / MDF-e — Sprint 5+
- ❌ Transmissão PGDAS-D ao SERPRO — Sprint 6
- ❌ IRPJ / CSLL / PIS / Cofins Lucro Presumido — Sprint 11
- ❌ Armazenamento do XML no S3 (`xml_storage_key`) — Sprint 5
- ❌ Rate limiting no upload — Sprint 6

## Próxima sprint

Sprint 3 — Camada IA: `LLMClient` unificado (Ollama + Gemma 3 + Gemini Flash Lite), cache de prompts, eval suite 100+ casos, CI roda eval.
