---
description: Roda os gates fiscais (golden + eval + mypy) e dá um parecer VERDE/VERMELHO
argument-hint: "[módulo opcional, ex: pessoal]"
---

# Validar fiscal $1

Acione o subagente **fiscal-validator** para validar os cálculos fiscais. Não pergunte confirmação a cada passo — execute e reporte ao final.

## Escopo
- Sem argumento: valida a suite fiscal inteira.
- Com `$1` (ex.: `pessoal`, `fiscal`, `lucro_presumido`, `icms`): foca o módulo, mas roda a suite cheia mesmo assim (golden é barreira global).

## O que o fiscal-validator roda
```powershell
$env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
cd C:\dev\Apresentação-Ideia\analista-fiscal-api
poetry run python -m pytest tests/unit tests/eval --tb=short
poetry run python -m mypy app/
```
E, se `$1` foi dado: `poetry run python -m pytest tests/unit/$1 -v`.

## Parecer (formato fixo)
```
VEREDITO: VERDE | VERMELHO
Testes: <passou>/<total> (unit+eval) · mypy: <ok | N erros>
Divergências (bloqueiam): …
Avisos: …
```
Se VERMELHO, nomeie o agente dono que deve corrigir e pare — não tente "consertar" cálculo aqui.
