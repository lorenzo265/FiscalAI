# ADR 0011 — Parser XML de NF-e: `defusedxml` em vez de `nfelib`

## Status

accepted (2026-05-20)

## Contexto

O `PlanoBackend.md` §3.2 lista `nfelib` como parser oficial de XML de NF-e/NFC-e na Sprint 2. Ao implementar `app/modules/ingestao/parser.py`, avaliamos a substituição.

Características relevantes:

- `nfelib` é a biblioteca brasileira mais conhecida para NF-e — modelos completos do leiaute 4.0/PL_009, usada pelo OpenERP/Erpbrasil.
- Backend só precisa extrair ~15 campos da NF-e (chave, número, série, CNPJs, valor total, impostos por bloco, CFOP/NCM do primeiro item, CRT do emitente, dhEmi). Não emite, não assina, não consulta SEFAZ no módulo `ingestao` — emissão é Sprint 5 via Focus NFe.
- `nfelib` carrega ~50MB de classes geradas por xsdata. Para parsing pontual de 15 campos, é peso morto.
- XXE e billion-laughs são vetores conhecidos em XML não confiável (NF-e chega via upload, IMAP e webhooks). `defusedxml` cobre os dois explicitamente; `nfelib` delega ao parser stdlib sem hardening adicional.

## Decisão

Adotar **`defusedxml.ElementTree`** como parser de XML NF-e/NFC-e no módulo `ingestao`. Não adicionar `nfelib` como dependência do MVP.

Localização canônica: `app/modules/ingestao/parser.py` — função `parse_xml_nfe(bytes) -> NFeData` (dataclass frozen, slots).

## Consequências

**Positivas:**

- Superfície de ataque controlada — `defusedxml` desabilita external entity loading, parameter entities e DTD por default (cobertura OWASP A05:2021).
- Dependência leve (~20 KB) versus ~50 MB de `nfelib`.
- Código auditável em ~150 linhas — toda extração visível em um único arquivo, sem indireções por modelos gerados.
- Sem acoplamento à versão do leiaute oficial: subir do PL_009 para PL_010 muda apenas a função de parsing local.

**Negativas:**

- Reimplementamos um subset minúsculo do que `nfelib` faria — se mais campos forem necessários (detalhamento por item, transporte, cobranças, parcelas), o custo de extensão cresce.
- Não temos validação contra XSD oficial — o que entra é o que o emissor declarou. Mitigação: SEFAZ já validou antes de autorizar; backend valida chave (44 dígitos), CNPJ (algoritmo), e campos obrigatórios.
- Divergência do Plano §3.2. Este ADR é o registro formal da decisão.

**Reversibilidade:** alta. Se precisarmos do leiaute completo (Sprint 16 SPED ECF importa NF-e em volume), basta adicionar `nfelib` no `pyproject.toml` e fazer parser híbrido. Os ~50 chamadores de `NFeData` continuam funcionando porque o dataclass é estável.

## Alternativas consideradas

- **`nfelib`** — modelo completo do leiaute, sem hardening anti-XXE explícito. Rejeitado pela superfície maior + dependência pesada para uso minúsculo.
- **`lxml` direto** — performance superior ao stdlib, mas precisaria de `resolve_entities=False` + `no_network=True` manualmente. `defusedxml` faz isso por default e é one-liner trocar quando necessário.
- **`xmlschema` + XSD oficial** — validaria contra o leiaute. Rejeitado: XSD da NF-e tem ~30 arquivos importados, build do schema é caro (>500ms cold), e SEFAZ já validou.

## Pendência rastreada

Quando a Sprint 16 (SPED ECF) precisar reconstruir histórico via importação de NF-e em massa, reabrir esta decisão — se >50% dos campos forem necessários, faz sentido carregar `nfelib`.
