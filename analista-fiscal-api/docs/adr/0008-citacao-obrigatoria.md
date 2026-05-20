# ADR 0008 — Citação obrigatória em respostas LLM

## Status

accepted (2026-05-10)

## Contexto

Alucinação de LLM em valores fiscais não é cosmética — gera multa real, juros e responsabilização do cliente. Casos típicos: o modelo "lembra" um valor de DAS errado, inventa uma alíquota, atribui uma NF-e a uma empresa errada. Sem mecanismo estrutural, esse risco é probabilístico e silencioso.

## Decisão

Toda resposta LLM exposta ao usuário **deve** incluir citações de IDs reais (UUID de `documento_fiscal`, `apuracao_fiscal`, `lancamento`, etc). A camada de validação:

1. O prompt sempre inclui as fontes disponíveis (`fontes_disponiveis: list[FonteRef]`) com IDs e trechos.
2. O response_schema Pydantic exige um campo `citacoes: list[FonteRef]` não vazio.
3. Após receber a resposta, `validar_resposta` checa que cada citação aponta para um ID realmente passado no contexto.
4. Re-check determinístico de valores monetários, datas e CNPJs contra as fontes.
5. Se falhar: rejeitar e retry com prompt reforçado. Segunda falha: retornar resposta padrão **"vou verificar com seu contador"**.

## Consequências

**Positivas:**
- Defesa estrutural contra alucinação — não depende de "qualidade do prompt".
- Auditoria — toda resposta LLM tem trilha verificável.
- Confiança do usuário — citações expostas no UI dão âncora visual.
- Métrica observável — taxa de "resposta padrão" virou KPI no §15 (alvo <2%).

**Negativas:**
- Latência maior — re-check + possível retry adiciona ~200–500ms p95.
- Custo maior — prompts mais longos (incluem fontes); compensa com cache.
- Algumas perguntas legítimas não têm fonte estruturada (ex: "como funciona Fator R?"). Mitigação: marcar perguntas conceituais e permitir resposta sem citação **apenas** quando classificadas como tal.

## Alternativas consideradas

- **Confiar no modelo** — rejeitado: risco existencial.
- **Apenas re-check de valores** — insuficiente; modelo pode inventar narrativa coerente sem números errados.
- **Apenas humano-no-loop** — inviável em volume; quebra a UX de WhatsApp.

## Referências

- `PlanoBackend.md` §6, §8.5, §8.6, §8.8
