---
tags: [dashboard, indice]
---

# 📊 Dashboard — Analista Fiscal

> Painéis vivos gerados pelo plugin **Dataview** a partir do frontmatter das notas.
> Requer: Settings → Community plugins → instalar e ativar **Dataview**.
> Se os blocos abaixo aparecerem como código (não como tabela), o Dataview não está ativo.

Hub de navegação: [[README]].

---

## ⚠️ Pendências abertas (por prioridade)

```dataview
TABLE WITHOUT ID
  file.link AS "Pendência",
  prioridade AS "Prioridade",
  status AS "Status",
  fonte AS "Fonte"
FROM "pendencias"
WHERE status != "resolvida"
SORT choice(prioridade = "alta", 0, choice(prioridade = "media", 1, 2)) ASC
```

## ✅ Pendências resolvidas

```dataview
LIST
FROM "pendencias"
WHERE status = "resolvida"
SORT file.name ASC
```

---

## 📦 Módulos (por status)

```dataview
TABLE WITHOUT ID
  file.link AS "Módulo",
  status AS "Status",
  sprint_origem AS "Sprint",
  path AS "Caminho"
FROM "modulos"
SORT status ASC, file.name ASC
```

---

## 🚀 Sprints

```dataview
TABLE WITHOUT ID
  file.link AS "Sprint",
  fase AS "Fase",
  status AS "Status",
  marco AS "Marco"
FROM "sprints"
SORT file.name ASC
```

---

## 🏛️ Princípios invioláveis

```dataview
TABLE WITHOUT ID
  file.link AS "Princípio",
  fonte AS "Fonte",
  status AS "Status"
FROM "principios"
SORT file.name ASC
```

---

## 📚 Decisões arquiteturais (ADRs)

```dataview
TABLE WITHOUT ID
  file.link AS "ADR",
  adr AS "Nº Plano",
  status AS "Status",
  fonte AS "Fonte"
FROM "decisoes"
SORT file.name ASC
```

---

## 🔎 Notas órfãs (sem links de entrada)

> Útil para achar notas que ninguém referencia — candidatas a linkar ou arquivar.

```dataview
LIST
FROM "principios" OR "modulos" OR "sprints" OR "decisoes" OR "pendencias"
WHERE length(file.inlinks) = 0
SORT file.name ASC
```
