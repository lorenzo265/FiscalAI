# Roadmap Escrituração Contábil — Tudo Que Falta Implementar

**Documento de trabalho para completar a camada contábil do Analista Fiscal.**  
Versão: 2.0 (auditada) | Última atualização: 2026-06-06  
> v2.0 corrige a v1.0 com o **estado real do código** (4 auditorias read-only). Leia o §1 e o
> §1.5 — eles substituem a visão original. O §2–§4 contêm código SPED **fictício**; não copiar.

---

## 📋 Índice

1. [Visão geral](#1-visão-geral)
2. [Tier 1 — Crítico (Sprint 16-18)](#2-tier-1--crítico-sprint-16-18)
3. [Tier 2 — Importante (Sprint 19-20)](#3-tier-2--importante-sprint-19-20)
4. [Tier 3 — Nice-to-have (Sprint 21-22)](#4-tier-3--nice-to-have-sprint-21-22)
5. [Golden tests obrigatórios](#5-golden-tests-obrigatórios)
6. [Checklists de implementação](#6-checklists-de-implementação)

---

## 1. Visão Geral

> ### ⚠️ CORREÇÃO DE BASELINE — Auditoria 2026-06-06 (substitui o §1 original e relativiza o §2+)
>
> A versão 1.0 deste documento (escrita em 2026-06-05) **não inspecionou o código real** e
> descreveu como "❌ faltando" um conjunto de coisas que **já estavam implementadas**. Quatro
> agentes de auditoria read-only varreram `app/modules/sped/**`, `app/modules/contabil/**`,
> `app/modules/migracao/**`, models/migrations/workers e o frontend. Achados consolidados abaixo.
>
> **Aviso de segurança técnica:** os exemplos de código SPED do §2 (registros `0-01`, `0-00`,
> `I-01`, `I-02`, `J-01`…) **são fictícios — NÃO são o leiaute RFB** e contêm campos em espanhol
> (`naturaleza`, `descripcion`). O leiaute real, pipe-delimitado `|REG|campo|…|` (`|0000|`, `|I050|`,
> `|J100|`, `|E110|`, `|9999|`), **já está implementado** em `app/modules/sped/`. **NÃO copie o
> código do §2.** Use os geradores existentes como gabarito.

### Estado REAL auditado (2026-06-06) — backend ~90% pronto

Suite: **2433 testes** verdes, mypy strict 0 erros, Sprints 0–22 fechadas + hardening + validação fiscal.

| Camada | Estado | Evidência |
|---|---|---|
| Plano de contas referencial (SCD Type 2, RLS) | ✅ (46 contas, mapeia `codigo_ecd_referencial`) | `contabil/plano_referencial.py:39` |
| Lançador automático: NF saída/entrada, transação, depreciação, provisão, folha | ✅ partida dobrada balanceada | `contabil/lancador_auto.py:219–527` |
| Encerramento mensal/anual + abertura + apuração de resultado (ARE) | ✅ idempotente | `contabil/encerramento_service.py:97–492` |
| Relatórios: balancete, razão, diário, DRE, balanço, DFC, indicadores | ✅ | `contabil/relatorios_service.py`, `relatorios/calcula_*.py` |
| Validação de partida dobrada (D=C, conta vigente/analítica/tenant) | ✅ robusta | `contabil/partidas.py:54–122` |
| **SPED ECD** (blocos 0/I/J/9, leiaute v10) | ✅ exceto J800/J900 | `sped/ecd/gerador.py` |
| **SPED ECF** (LP completo, K/P/…) | ✅ exceto 0930/Y600 | `sped/ecf/gerador.py` |
| **SPED EFD-Contribuições** (PIS/Cofins cumulativo, v1.36) | ✅ exceto granularidade/M400/M800 | `sped/efd/gerador_contribuicoes.py` |
| **SPED EFD ICMS-IPI** (v3.1.7, E110/CIAP) | ✅ exceto 0200/H010 | `sped/efd/gerador_icms_ipi.py` |
| Validador SPED (9990/9999/9900, D=C, P200/P300, E110) | ✅ amplo | `sped/validador.py` |
| **Importador histórico** (parsers ECD/ECF/EFD-Contrib/EFD-ICMS/CSV + idempotência) | ✅ backend | `migracao/service.py`, `migracao/parser_*.py` |
| Migrations RLS + índices de performance (0014/0015/0039/0040/0041) | ✅ | `alembic/versions/004*` |
| Workers SPED mensal/anual (lógica real; Celery opt-in) | ✅ (stub se sem Celery) | `workers/tasks/sped_gerar_*.py` |

### O que REALMENTE falta (gaps cirúrgicos) — ver §1.5

O grande buraco é o **frontend** (zero UI de SPED/importador, encerramento simulado) e, no backend,
**impostos apurados que nunca viram lançamento contábil** (DAS/IRPJ/CSLL/PIS/Cofins/ICMS/ISS) + 3
correções de SPED que travam o PVA. **Performance e o grosso de "event-driven" do §3 já existem ou
não são gargalo** — não repetir esse trabalho.

---

## 1.5 Gap Analysis Auditado (2026-06-06) — o que falta para "escrituração 100%"

Severidade: 🔴 crítico (corretude legal / trava PVA) · 🟠 alto (material) · 🟡 médio.

### A. Backend — Impostos apurados não viram lançamento (maior gap de corretude)
| # | Gap | Sev | Evidência |
|---|---|---|---|
| A1 | **DAS não é contabilizado** — conta `2.1.4.01` existe, mas não há `gerar_partidas_de_das`/`lote_das`. Todo DAS apurado some do balanço/DRE | 🔴 | `contabil/lancador_auto.py` (ausente) |
| A2 | **IRPJ/CSLL/PIS/Cofins (LP) não contabilizados** — sem conta `2.1.4.x` e sem função | 🟠 | `plano_referencial.py`, `lancador_auto.py` (ausente) |
| A3 | **ICMS/ISS a recolher não contabilizados** — sem conta e sem função | 🟠 | idem |
| A4 | Plano sem **Passivo Não-Circulante (2.2)**, **Resultado Financeiro**, **Deduções/devoluções (retificadora 4.x)**, **Distribuição de Lucros (3.x)** → BP mostra PNC=0, DRE resultado financeiro=0 | 🟠 | `plano_referencial.py`; `calcula_dre.py:187`; `calcula_balanco.py`/`calcula_dfc.py` (prefixo `2.2` nunca casa) |

### B. Backend — Robustez/cobertura do lançador
| # | Gap | Sev | Evidência |
|---|---|---|---|
| B1 | **Mapa CFOP só cobre 10 CFOPs** — ~25 comuns (devolução venda/compra, uso/consumo, embalagem) caem em "5.1.99 — A Classificar" | 🟠 | `classificador_cfop.py:34–50` |
| B2 | **Motor automático não bloqueia mês encerrado** — `lote_nfe/transacao/depreciacao/provisao` não chamam `competencia_encerrada` (fato retroativo entra em mês fechado) | 🟠 | `lancador_service.py:126–376` |
| B3 | `lote_folha` **não exposto via REST** e ausente do enum `TipoFatoAuto` | 🟡 | `router.py:231`, `schemas.py:133` |
| B4 | Motor automático não re-valida partidas (defense-in-depth) | 🟡 | `lancador_service.py._persistir` |

### C. Backend — SPED: completar para aceitação no PVA
| # | Gap | Sev | Evidência |
|---|---|---|---|
| C1 | **ECF sem registro 0930** (signatário/CPF do contador) → PVA não permite transmitir | 🔴 | `sped/ecf/gerador.py:332` |
| C2 | **EFD ICMS-IPI sem registro 0200** (tabela de itens) → C170 referencia `MERC-GENERICO` não cadastrado → erro estrutural no PVA | 🔴 | `sped/efd/gerador_icms_ipi.py:432` |
| C3 | **ECF Y600 (sócios) sempre vazio** + P030/Y540 atividade `"01"` hardcoded (errado p/ serviços 32%) → declaração incompleta, multa | 🟠 | `sped/ecf/service.py:290`, `gerador.py:493` |
| C4 | **Endereço sempre vazio** em 0030/0005/0100 (TIP_LOG/LOG/NUM/COMPL/BAIRRO = `""`) — carregar do cadastro (cross-cutting nos 4 geradores) | 🟠 | `ecd/gerador.py:334`, `efd/*:378` |
| C5 | ECD **J800** (notas explicativas, LP>R$2M) + **J900** (termo de encerramento do bloco J) | 🟡 | `sped/ecd/gerador.py` (ausente) |
| C6 | EFD-Contrib: 0190 só `UN`; **M400/M800** placeholders (`VL_TOT_REC=0`); A170/C100 granularidade por item | 🟡 | `efd/gerador_contribuicoes.py:771,802` |
| C7 | EFD ICMS-IPI: **H010 inventário** (estoque), E116 `COD_REC` por UF, C190 multi-CFOP | 🟡 | `efd/gerador_icms_ipi.py:761,237` |
| C8 | Validador: amarração **M200 vs Σ A170/C170** (adiada) | 🟡 | `sped/validador.py:795` |

### D. Backend — Storage / async / event-driven / housekeeping
| # | Gap | Sev | Evidência |
|---|---|---|---|
| D1 | SPED grava em **BYTEA do Postgres**, não em ObjectStorage; `storage_key` sempre NULL (infla DB em escala) | 🟠@escala | `sped/*/service.py`; `S3Storage` existe mas inativo |
| D2 | **Endpoint de processamento assíncrono de migração ausente** — task existe, sem trigger HTTP/presigned (arquivos >50MB travam o request síncrono) | 🟠 | `workers/tasks/migracao_processar_lote.py:18` |
| D3 | **Lançamento contábil não é event-driven** — NF ingerida (Focus/SEFAZ) / transação (Pluggy) não dispara `lote_*`; contador precisa acionar manualmente | 🟠 | ausente em `ingestao/`, `open_finance/` |
| D4 | Workers SPED rodam `select(Empresa)` cross-tenant **sem `SET LOCAL`/role BYPASSRLS documentado** | 🟡 | `sped_gerar_anual.py:136` |
| D5 | Migration **0056** (`ck_lanc_origem_tipo` + `'folha'`) está **untracked** no git — model Python já usa `'folha'`; se 0056 não entrar na chain, `fechar_folha` quebra em prod | 🔴-prod | `git status: ?? .../0056_*.py` |
| D6 | Sem materialized view de balancete (perf futura); `S3Storage.put_object` síncrono em corrotina | 🟡 | — |

### E. Frontend — o grande buraco visível (entregável do contador)
| # | Gap | Sev | Evidência |
|---|---|---|---|
| E1 | **Zero UI de SPED** — nenhuma tela para gerar/validar/baixar ECD/ECF/EFD. É o principal entregável de escrituração | 🔴 | busca `sped/ecd/ecf/efd` em `src/` → nada |
| E2 | **Encerramento é simulado** — botão "Fechar" usa `setTimeout(2.4s)`, não chama o backend | 🔴 | `app/(dashboard)/contabil/encerramento/page.tsx:75` |
| E3 | **Sem confirmação rascunho→confirmado** — lançamentos automáticos ficam eternamente em rascunho na ótica da UI | 🟠 | (ação ausente) |
| E4 | **Sem tela de plano de contas** (endpoint já consumido pelo adapter, sem superfície) | 🟠 | `lib/api/contabil.ts` (existe), tela ausente |
| E5 | **Motor client-side usa plano hardcoded local** → contas reais do backend aparecem sem nome (divergência silenciosa) | 🟠 | `lib/contabil/motor.ts`, `buscarConta()` |
| E6 | **Sem importador UI** (upload CSV/SPED histórico) — empresa com histórico não migra | 🟠 | (tela ausente) |
| E7 | Sem seletor de competência nas telas; sem estorno na UI; sem export PDF de DRE/Balanço/DFC | 🟡 | — |

### F. Testes
Golden tests novos para cada lançador de imposto, CFOPs adicionados e novos registros SPED; manter o gate (pytest+mypy) verde a cada PR.

### Sequência de implementação recomendada (ondas)

```
WAVE 1 (backend, corretude dos livros) ── impostos viram lançamento + plano completo + lançador hardening
        A1 A2 A3 A4 · B1 B2 B3 B4 · D5(commit 0056) · golden
WAVE 2 (backend, regulatório SPED PVA) ── C1 C2 C3 C4 (+ C5 se LP>2M) · validador C8 · bump ALGORITMO_VERSAO
WAVE 3 (backend, infra/produto) ──────── D1 storage · D2 async migração · D3 event-driven auto-lançamento · D4
WAVE 4 (frontend, Arkan) ─────────────── E1 SPED UI · E2 encerramento real · E3 confirmar · E4 plano · E5 motor · E6 importador · E7
```

WAVE 1 e WAVE 4 são as de maior valor (corretude + entregável visível). WAVE 2 é pré-requisito de
go-live com transmissão real. WAVE 3 é escala/operacional. §2–§4 abaixo ficam como **referência
histórica** — releve qualquer item já marcado ✅ na tabela de Estado Real acima.

---

## 2. Tier 1 — Crítico (Sprint 16-18)

### 2.1 SPED ECD — Escrituração Contábil Digital (Sprint 16)

**Escopo:** Gerar arquivo `.txt` no formato RFB, validar localmente, permitir download.

**Por que crítico:** Obrigação anual até 31/maio; inclusa na "cobertura de Fase 3"; sem ECD, não há Lucro Real/Presumido pronto para produção.

#### 2.1.1 Estrutura de pastas

```
app/shared/sped/
├── __init__.py
├── layouts.py              # Definições dos blocos (schemas)
├── validators.py           # Validador local
├── ecd_generator.py        # Gerador ECD
├── ecf_generator.py        # Gerador ECF
├── efd_contribuicoes.py    # EFD-Contribuições (Sprint 17)
└── efd_icms_ipi.py         # EFD ICMS-IPI (Sprint 17)
```

#### 2.1.2 Schema: `app/shared/sped/layouts.py`

```python
"""Definições de blocos SPED — Layout RFB 2025+."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

# ────────────────────────────────────────────────────────────────────────────
# BLOCO 0 — Abertura
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LinhaProdutoRFB:
    """Linha 0-01: identificação do arquivo."""
    linha: Literal["0-01"]
    data_extracao: date
    hora_extracao: str        # HH:MM:SS
    data_atualizacao: date
    hora_atualizacao: str     # HH:MM:SS
    formato: Literal["1"]     # 1 = SPED digital
    versao_layout: str        # ex: "15.0.0" (COTEPE/ICMS 2025)
    num_sequencial_arq: int   # 1-based
    nome_arquivo: str

@dataclass(frozen=True)
class LinhaEmpresaRFB:
    """Linha 0-00: informações da empresa."""
    linha: Literal["0-00"]
    tipo_inscricao: int       # 1=CNPJ, 2=CPF
    inscricao: str            # 14 ou 11 dígitos
    uf_participante: str      # 2 letras
    nome_participante: str
    nome_fantasia: str | None
    logradouro: str
    numero: str
    complemento: str | None
    bairro: str
    cep: str                  # 8 dígitos
    municipio: str            # nome
    municipio_ibge: str       # 7 dígitos
    telefone: str | None
    email: str | None
    contato: str | None
    atividade_fiscal: int     # 1=industrial, 2=comercial, 3=serviços, 4=pref. social

@dataclass(frozen=True)
class LinhaEncerramento:
    """Linha 9-99: encerramento."""
    linha: Literal["9-99"]
    num_linhas: int           # contagem de linhas (0-00 até última linha antes desta)
    chave_validacao: str | None  # CRC ou hash (opcional, RFB valida)

# ────────────────────────────────────────────────────────────────────────────
# BLOCO I — Informações contábeis
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LinhaContaContabil:
    """Linha I-01: plano de contas."""
    linha: Literal["I-01"]
    conta: str                # código conta (ex: "1.1.01.01")
    nome_conta: str
    nivel: int                # 1-4
    conta_pai: str | None     # NULL se nível 1
    natureza: Literal["A", "P", "PL", "R", "D"]  # ativo, passivo, patrimônio, receita, despesa
    descricao_tipo: str | None

@dataclass(frozen=True)
class LinhaLancamento:
    """Linha I-02: lançamento contábil."""
    linha: Literal["I-02"]
    natop: str                # natureza operação (fiscal)
    descr: str
    data_lancamento: date
    valor: Decimal
    indicador_debcred: Literal["D", "C"]  # débito ou crédito
    conta: str                # código da conta
    contapartida: str         # contra-partida
    historico: str | None
    valor_complementar: Decimal | None
    num_documento_origem: str | None
    tipo_documento: str | None

# ────────────────────────────────────────────────────────────────────────────
# BLOCO J — Balancete e encerramento
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LinhaBalancete:
    """Linha J-01: balancete final."""
    linha: Literal["J-01"]
    conta: str
    saldo: Decimal            # signed
    indicador_debcred: Literal["D", "C"]

@dataclass(frozen=True)
class LinhaResultado:
    """Linha J-02: apuração de resultado (lucro/prejuízo)."""
    linha: Literal["J-02"]
    descripcion: str
    valor_receita: Decimal
    valor_despesa: Decimal
    resultado: Decimal        # receita - despesa
```

#### 2.1.3 Gerador: `app/shared/sped/ecd_generator.py`

```python
"""Gerador de ECD — Escrituração Contábil Digital (Sprint 16)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import AsyncIterable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.relatorios_service import RelatoriosService
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.models import ContaContabil, LancamentoContabil
from app.shared.exceptions import EmpresaNaoEncontrada, PlanoContasIncompleto
from app.shared.sped.layouts import (
    LinhaProdutoRFB,
    LinhaEmpresaRFB,
    LinhaContaContabil,
    LinhaLancamento,
    LinhaBalancete,
    LinhaResultado,
    LinhaEncerramento,
)

log = structlog.get_logger(__name__)

ALGORITMO_VERSAO = "ecd-2026.01"  # Sprint 16


class ECDGerador:
    """Gerador determinístico de ECD sem I/O (recebe data já carregada)."""

    def __init__(self):
        self.linhas: list[str] = []
        self.num_linhas = 0

    def gerar_bloco_0(
        self,
        empresa_cnpj: str,
        empresa_uf: str,
        empresa_nome: str,
        empresa_fantasia: str | None,
        data_fechamento: date,
    ) -> None:
        """Bloco 0 — Abertura e identificação."""
        agora = datetime.now()
        
        # 0-01: Identificação
        self._adicionar_linha([
            "0-01",
            data_fechamento.strftime("%d%m%Y"),
            agora.strftime("%H%M%S"),
            date.today().strftime("%d%m%Y"),
            agora.strftime("%H%M%S"),
            "1",  # digital
            "15.0.0",  # versão layout COTEPE 2025
            "1",  # sequencial
            f"ECD{empresa_cnpj}{data_fechamento.strftime('%Y%m%d')}.txt",
        ])

        # 0-00: Empresa
        self._adicionar_linha([
            "0-00",
            "1",  # CNPJ
            empresa_cnpj,
            empresa_uf,
            empresa_nome,
            empresa_fantasia or "",
            "Rua Exemplo",  # TODO: carregar do cadastro
            "0",
            "",
            "Centro",
            "00000000",
            "São Paulo",
            "3550308",  # IBGE SP capital
            "",
            "",
            "",
            "2",  # comercial
        ])

    def gerar_bloco_i(
        self,
        contas: list[ContaContabil],
        lancamentos: list[LancamentoContabil],
        periodo_inicio: date,
        periodo_fim: date,
    ) -> None:
        """Bloco I — Informações contábeis."""
        
        # I-01: Plano de contas
        for conta in sorted(contas, key=lambda c: c.codigo):
            if conta.valid_to is not None:
                continue  # Pula contas canceladas
            
            self._adicionar_linha([
                "I-01",
                conta.codigo,
                conta.descricao[:60],  # trunca a 60 chars
                str(conta.nivel),
                conta.parent_id.hex[:8] if conta.parent_id else "",
                _naturaleza_para_letra(conta.natureza),
                "S" if conta.aceita_lancamento else "N",
            ])

        # I-02: Lançamentos
        for lancamento in sorted(lancamentos, key=lambda l: l.data_lancamento):
            if lancamento.status == "rascunho":
                continue  # Pula rascunhos
            
            for partida in lancamento.partidas:
                self._adicionar_linha([
                    "I-02",
                    "4",  # natureza operação (outro)
                    lancamento.historico[:60],
                    lancamento.data_lancamento.strftime("%d%m%Y"),
                    str(partida.valor).replace(".", "").rjust(14, "0"),
                    partida.tipo,
                    partida.conta.codigo,
                    "0",  # contra-partida (simplificado)
                    "",
                ])

    def gerar_bloco_j(
        self,
        saldos_finais: dict[str, Decimal],
        resultado_exercicio: Decimal,
    ) -> None:
        """Bloco J — Balancete e apuração de resultado."""
        
        # J-01: Balancete
        for conta_codigo, saldo in sorted(saldos_finais.items()):
            indicador = "D" if saldo >= 0 else "C"
            self._adicionar_linha([
                "J-01",
                conta_codigo,
                str(abs(saldo)).replace(".", "").rjust(14, "0"),
                indicador,
            ])

        # J-02: Resultado
        self._adicionar_linha([
            "J-02",
            "Lucro do Exercício" if resultado_exercicio >= 0 else "Prejuízo do Exercício",
            "",
            str(abs(resultado_exercicio)).replace(".", "").rjust(14, "0"),
        ])

    def gerar_bloco_9(self) -> None:
        """Bloco 9 — Encerramento."""
        self._adicionar_linha([
            "9-99",
            str(self.num_linhas + 1),  # +1 para contar a própria linha
            "",  # chave (opcional)
        ])

    def _adicionar_linha(self, campos: list[str]) -> None:
        """Adiciona linha formatada (pipe-delimitado)."""
        linha = "|".join(str(c) for c in campos) + "|"
        self.linhas.append(linha)
        self.num_linhas += 1

    def exportar(self) -> str:
        """Retorna arquivo completo como string."""
        return "\n".join(self.linhas)


def _naturaleza_para_letra(natureza: str) -> str:
    """Mapeia natureza da conta para letra RFB."""
    mapa = {
        "ativo": "A",
        "passivo": "P",
        "patrimonio": "PL",
        "receita": "R",
        "despesa": "D",
    }
    return mapa.get(natureza, "A")


class ECDService:
    """Service que orquestra geração de ECD com I/O."""

    async def gerar_ecd(
        self,
        session: AsyncSession,
        tenant_id,
        empresa_id,
        ano: int,
    ) -> tuple[str, str]:
        """Gera ECD para um ano completo.

        Returns:
            (arquivo_txt, hash_sha256)
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id}")

        # Carrega plano de contas vigente
        contas = await ContaContabilRepo(session).listar_vigentes(empresa_id)
        if not contas:
            raise PlanoContasIncompleto(f"Empresa {empresa_id} sem plano de contas")

        # Carrega lançamentos do ano
        lancamentos = await LancamentoRepo(session).por_periodo(
            empresa_id,
            date(ano, 1, 1),
            date(ano, 12, 31),
        )

        # Carrega saldos finais (dezembro)
        relatorios_svc = RelatoriosService()
        balancete = await relatorios_svc.balancete(
            session, empresa_id, date(ano, 12, 1)
        )
        saldos = {linha.conta.codigo: linha.saldo for linha in balancete}

        # Gera
        gerador = ECDGerador()
        gerador.gerar_bloco_0(
            empresa.cnpj,
            empresa.uf,
            empresa.razao_social,
            empresa.nome_fantasia,
            date(ano, 12, 31),
        )
        gerador.gerar_bloco_i(contas, lancamentos, date(ano, 1, 1), date(ano, 12, 31))
        gerador.gerar_bloco_j(saldos, Decimal("0"))  # TODO: calcular resultado
        gerador.gerar_bloco_9()

        arquivo_txt = gerador.exportar()

        # Hash para integridade
        import hashlib
        hash_sha256 = hashlib.sha256(arquivo_txt.encode()).hexdigest()

        log.info(
            "sped.ecd.gerada",
            empresa_id=str(empresa_id),
            ano=ano,
            num_linhas=gerador.num_linhas,
            hash=hash_sha256,
        )

        return arquivo_txt, hash_sha256
```

#### 2.1.4 Validador: `app/shared/sped/validators.py`

```python
"""Validador local de SPED (amarrações, somas, DNCs)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

@dataclass
class ErroValidacao:
    tipo: Literal["erro", "aviso"]
    codigo: str
    descricao: str
    linha_numero: int | None = None
    valor_esperado: str | None = None
    valor_observado: str | None = None


class ValidadorSPED:
    """Validador determinístico (sem I/O)."""

    def __init__(self, arquivo_txt: str):
        self.linhas = arquivo_txt.strip().split("\n")
        self.erros: list[ErroValidacao] = []

    def validar_bloco_0(self) -> list[ErroValidacao]:
        """Valida abertura e estrutura."""
        erros = []
        
        # Primeira linha deve ser 0-01
        if self.linhas[0] != "0-01":
            erros.append(ErroValidacao(
                tipo="erro",
                codigo="BLO0_001",
                descricao="Primeira linha deve ser 0-01 (identificação)",
                linha_numero=1,
            ))

        # Primeira linha de empresa deve ser segunda
        if not self.linhas[1].startswith("0-00"):
            erros.append(ErroValidacao(
                tipo="erro",
                codigo="BLO0_002",
                descricao="Segunda linha deve ser 0-00 (empresa)",
                linha_numero=2,
            ))

        return erros

    def validar_bloco_j(self) -> list[ErroValidacao]:
        """Valida amarrações de balancete."""
        erros = []
        
        # Soma débitos == soma créditos
        total_debito = Decimal("0")
        total_credito = Decimal("0")

        for i, linha in enumerate(self.linhas, 1):
            if linha.startswith("J-01"):
                campos = linha.split("|")
                if len(campos) >= 4:
                    valor_str = campos[2]
                    indicador = campos[3]
                    try:
                        valor = Decimal(valor_str) / 100  # centavos
                        if indicador == "D":
                            total_debito += valor
                        else:
                            total_credito += valor
                    except:
                        pass

        if total_debito != total_credito:
            erros.append(ErroValidacao(
                tipo="erro",
                codigo="BALJ_001",
                descricao=f"Balancete desbalanceado: débito {total_debito} != crédito {total_credito}",
                valor_esperado=str(total_debito),
                valor_observado=str(total_credito),
            ))

        return erros

    def validar(self) -> list[ErroValidacao]:
        """Executa todas as validações."""
        return (
            self.validar_bloco_0() +
            self.validar_bloco_j() +
            []  # Adicionar mais validadores
        )
```

#### 2.1.5 Endpoint: `app/modules/contabil/router.py`

```python
"""Adicionar ao router existente."""

from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from app.shared.db.deps import get_session, get_tenant_context
from app.modules.contabil.schemas import ArquivoSPEDOut
from app.shared.sped.ecd_generator import ECDService

router = APIRouter(prefix="/api/v1/contabil", tags=["contabil"])

@router.post("/sped/ecd/{empresa_id}/{ano}/gerar")
async def gerar_ecd(
    empresa_id: UUID,
    ano: int,
    session = Depends(get_session),
    tenant_context = Depends(get_tenant_context),
) -> ArquivoSPEDOut:
    """Gera ECD para um ano e persiste em storage."""
    
    if ano < 2020 or ano > 2100:
        raise HTTPException(status_code=400, detail="Ano inválido")

    svc = ECDService()
    arquivo_txt, hash_sha256 = await svc.gerar_ecd(
        session, tenant_context.tenant_id, empresa_id, ano
    )

    # TODO: Validar
    # validador = ValidadorSPED(arquivo_txt)
    # erros = validador.validar()

    # TODO: Persistir em S3
    # storage_key = f"sped/ecd/{empresa_id}/{ano}.txt"
    # await upload_s3(arquivo_txt, storage_key)

    # TODO: Persistir metadata em BD
    # arquivo_sped = await ArquivoSPEDRepo(session).criar(
    #     tenant_id=tenant_context.tenant_id,
    #     empresa_id=empresa_id,
    #     tipo="ecd",
    #     periodo_inicio=date(ano, 1, 1),
    #     periodo_fim=date(ano, 12, 31),
    #     storage_key=storage_key,
    #     hash_arquivo=hash_sha256,
    #     status="gerado",
    # )

    return ArquivoSPEDOut(
        id=uuid.uuid4(),  # Será atribuído no BD
        tipo="ecd",
        periodo_inicio=f"{ano}-01-01",
        periodo_fim=f"{ano}-12-31",
        status="gerado",
        num_linhas=arquivo_txt.count("\n"),
        hash_arquivo=hash_sha256,
        download_url=f"/api/v1/contabil/sped/ecd/{empresa_id}/{ano}/download",
    )

@router.get("/sped/ecd/{empresa_id}/{ano}/download")
async def baixar_ecd(
    empresa_id: UUID,
    ano: int,
    session = Depends(get_session),
):
    """Baixa arquivo ECD gerado como .txt."""
    # TODO: Validar permissão, buscar em S3, retornar como file response
    pass
```

#### 2.1.6 Schemas: `app/modules/contabil/schemas.py`

```python
"""Adicionar ao schemas existente."""

from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

class ArquivoSPEDOut(BaseModel):
    id: str
    tipo: str  # 'ecd' | 'ecf' | 'efd_contribuicoes' | 'efd_icms_ipi'
    periodo_inicio: str  # YYYY-MM-DD
    periodo_fim: str
    status: str  # 'gerado' | 'validado' | 'transmitido' | 'aceito' | 'rejeitado'
    num_linhas: int
    hash_arquivo: str
    download_url: str
    validacao_erros: Optional[list] = None
    validacao_avisos: Optional[list] = None
```

#### 2.1.7 Testes: `tests/unit/contabil/test_ecd_generator.py`

```python
"""Golden tests para geração de ECD."""

import pytest
from datetime import date
from decimal import Decimal
from app.shared.sped.ecd_generator import ECDGerador
from app.shared.sped.validators import ValidadorSPED

def test_ecd_bloco_0_abertura():
    """ECD deve conter bloco 0-01 de identificação."""
    gerador = ECDGerador()
    gerador.gerar_bloco_0(
        empresa_cnpj="11222333000181",
        empresa_uf="SP",
        empresa_nome="Empresa Teste Ltda",
        empresa_fantasia="Empresa Teste",
        data_fechamento=date(2025, 12, 31),
    )
    
    arquivo = gerador.exportar()
    assert "0-01|" in arquivo
    assert "11222333000181" in arquivo

def test_ecd_balancete_balanceado():
    """Balancete em bloco J-01 deve ter soma débitos = créditos."""
    gerador = ECDGerador()
    
    # Simula saldos: Caixa 1.000 (D) e Capital 1.000 (C)
    saldos = {
        "1.1.01.01": Decimal("1000.00"),  # débito
        "2.1.01.01": Decimal("-1000.00"),  # crédito
    }
    
    gerador.gerar_bloco_j(saldos, Decimal("0"))
    
    arquivo = gerador.exportar()
    validador = ValidadorSPED(arquivo)
    erros = validador.validar_bloco_j()
    
    assert len(erros) == 0, f"Balancete desbalanceado: {erros}"

def test_validador_primeira_linha_0_01():
    """Validador detecta se primeira linha não é 0-01."""
    arquivo_invalido = """0-00|...|
9-99|1|"""
    
    validador = ValidadorSPED(arquivo_invalido)
    erros = validador.validar()
    
    assert any(e.codigo == "BLO0_001" for e in erros)

def test_ecd_gera_arquivo_valido():
    """Fluxo completo: gera → exporta → valida."""
    gerador = ECDGerador()
    gerador.gerar_bloco_0("11222333000181", "SP", "Teste", "Teste", date(2025, 12, 31))
    gerador.gerar_bloco_9()
    
    arquivo = gerador.exportar()
    validador = ValidadorSPED(arquivo)
    erros = validador.validar()
    
    # Deve haver apenas avisos/validações secundárias, não erros críticos
    erros_criticos = [e for e in erros if e.tipo == "erro"]
    assert len(erros_criticos) == 0
```

---

### 2.2 SPED ECF — Escrituração Contábil-Fiscal (Sprint 16)

**Escopo:** Similar ao ECD, mas inclui blocos fiscais (C, D, E, F, H) além de contábeis.

**Diferenças principais:**
- Inclui operações fiscais por natureza (saída, entrada, etc)
- Reconcilia com notas fiscais (NF-e, NFS-e)
- Mais validações de amarração (ICMS, IPI, PIS, Cofins)
- Deadline: 31/julho

#### 2.2.1 Estrutura similar a ECD

```python
# app/shared/sped/ecf_generator.py

class ECFGerador:
    """Gerador ECF com blocos fiscais."""

    def gerar_bloco_c(self, documentos_fiscais: list):
        """Bloco C — operações de saída."""
        for doc in documentos_fiscais:
            if doc.direcao != "saida":
                continue
            # Formato: C-100 (documento), C-101 (item), C-190 (totalizador)
            self._adicionar_linha([
                "C-100",
                "55",  # tipo NF-e
                doc.numero,
                doc.serie,
                doc.emitida_em.strftime("%d%m%Y"),
                doc.cfop,
                doc.cnpj_destinatario,
                str(doc.valor_total).replace(".", "").rjust(14, "0"),
                doc.chave,
            ])

    def gerar_bloco_d(self, documentos_fiscais: list):
        """Bloco D — operações de entrada."""
        # Similar ao C, mas para entrada

    def gerar_bloco_e(self, notas_saida: list):
        """Bloco E — complemento de saída (ICMS, IPI, ISS)."""
        for nota in notas_saida:
            # Detalhamento de impostos retidos/recolhidos
            pass

    def gerar_bloco_f(self, notas_entrada: list):
        """Bloco F — complemento de entrada."""
        pass

    def gerar_bloco_h(self, inventarios: list):
        """Bloco H — inventário (opcional, se há estoque)."""
        pass
```

#### 2.2.2 Validações ECF

```python
# app/shared/sped/validators.py — adicionar

def validar_bloco_c_vs_nfe(self):
    """Valida se operações em bloco C batem com NF-e registradas."""
    # Soma valores em bloco C (campos "C-100")
    # Compara com soma de DocumentoFiscal.direcao='saida'
    # Se diferença > tolerância, erro
    pass

def validar_amarracoes_icms(self):
    """Valida se ICMS em bloco E reconcilia com apuração fiscal."""
    pass
```

#### 2.2.3 Teste ECF

```python
# tests/unit/contabil/test_ecf_generator.py

def test_ecf_bloco_c_operacoes_saida():
    """ECF bloco C deve listar todas as NFs de saída."""
    pass

def test_ecf_reconcilia_com_balancete():
    """ECF balancete final deve bater com contábil."""
    pass
```

---

### 2.3 EFD-Contribuições (Sprint 17)

**Escopo:** Apuração mensal de PIS e Cofins para Lucro Presumido/Real.

**Blocos principais:**
- 0: Identificação
- A: Operações tributáveis
- B: Operações não-tributáveis
- C: Créditos
- E: Apuração PIS
- F: Apuração Cofins
- 9: Encerramento

**Fórmula simplificada:**
```
Cofins = (receita_tributada × 7.6%) + (receita_nao_tributada × taxa_dif)
PIS = (receita_tributada × 1.65%) + (receita_nao_tributada × taxa_dif)
Crédito = crédito_operacional_acumulado
Saldo = (apuracao - crédito)
```

#### 2.3.1 Gerador EFD-Contribuições

```python
# app/shared/sped/efd_contribuicoes.py

class EFDContribuicoesGerador:
    """Gerador EFD-Contribuições mensal."""

    def __init__(self, competencia: date):
        self.competencia = competencia
        self.linhas = []

    def gerar_bloco_a(self, notas_saida: list):
        """Bloco A — operações tributáveis."""
        for nota in notas_saida:
            if nota.regime_icms == "normal":
                self._adicionar_linha([
                    "A-100",
                    "55",  # NF-e
                    nota.numero,
                    nota.serie,
                    nota.chave,
                    str(nota.valor_total).replace(".", "").rjust(14, "0"),
                    "1",  # tributável
                ])

    def gerar_bloco_e(self, receita_tributada: Decimal, credito: Decimal):
        """Bloco E — apuração PIS."""
        pis_due = receita_tributada * Decimal("0.0165")
        saldo_pis = pis_due - credito
        
        self._adicionar_linha([
            "E-100",
            str(receita_tributada).replace(".", "").rjust(14, "0"),
            str(pis_due).replace(".", "").rjust(14, "0"),
            str(credito).replace(".", "").rjust(14, "0"),
            str(saldo_pis).replace(".", "").rjust(14, "0"),
        ])

    def gerar_bloco_f(self, receita_tributada: Decimal, credito: Decimal):
        """Bloco F — apuração Cofins."""
        cofins_due = receita_tributada * Decimal("0.076")
        saldo_cofins = cofins_due - credito
        
        self._adicionar_linha([
            "F-100",
            str(receita_tributada).replace(".", "").rjust(14, "0"),
            str(cofins_due).replace(".", "").rjust(14, "0"),
            str(credito).replace(".", "").rjust(14, "0"),
            str(saldo_cofins).replace(".", "").rjust(14, "0"),
        ])
```

#### 2.3.2 Teste EFD-Contribuições

```python
# tests/golden/contabil/test_efd_contribuicoes_golden.py

def test_efd_contribuicoes_empresa_lp_janeiro_2025():
    """
    Empresa LP: receita R$100k em jan/2025
    Crédito acumulado R$2k
    
    PIS = 100k × 1.65% = 1.650
    Cofins = 100k × 7.6% = 7.600
    Saldo PIS = 1.650 - 2.000 = −350 (crédito)
    Saldo Cofins = 7.600 - 2.000 = 5.600 (débito)
    """
    # Carregar snapshot empresa
    # Gerar EFD
    # Validar blocos E e F batem valores
    pass
```

---

### 2.4 EFD ICMS-IPI (Sprint 17)

**Escopo:** Apuração mensal de ICMS e IPI.

**Blocos:**
- 0, A, B, C, D (ICMS), E (IPI), F, H, 9

Lógica similar a EFD-Contribuições, mas com múltiplas alíquotas por estado.

```python
# app/shared/sped/efd_icms_ipi.py

class EFDICMSIPIGerador:
    """Gerador EFD ICMS-IPI mensal."""

    def gerar_bloco_c(self, notas_saida: list, uf_empresa: str):
        """Bloco C — ICMS saída (operações internas)."""
        for nota in notas_saida:
            if nota.uf_destino == uf_empresa:
                # ICMS interno
                icms = nota.valor_total * Decimal(nota.aliquota_icms / 100)
                self._adicionar_linha([
                    "C-100",
                    "55",  # NF-e
                    nota.numero,
                    nota.serie,
                    nota.chave,
                    str(nota.valor_total).replace(".", "").rjust(14, "0"),
                    str(icms).replace(".", "").rjust(14, "0"),
                    nota.aliquota_icms,
                ])

    def gerar_bloco_d(self, notas_saida: list, uf_empresa: str):
        """Bloco D — ICMS saída (operações interestaduais)."""
        for nota in notas_saida:
            if nota.uf_destino != uf_empresa:
                # ICMS interestadual (alíquota reduzida)
                aliquota_dest = self._obter_aliquota_icms(nota.uf_destino)
                icms = nota.valor_total * Decimal(aliquota_dest / 100)
                self._adicionar_linha([
                    "D-100",
                    # Campos similares ao C
                ])
```

---

## 3. Tier 2 — Importante (Sprint 19-20)

### 3.1 Golden Tests Completos — Cobertura >95%

**Objetivo:** Cada tipo de lançamento automático tem ≥3 casos de teste pretos (entrada/saída típica, edge cases, erros).

#### 3.1.1 Estrutura de testes

```
tests/golden/contabil/
├── empresas/
│   ├── sn_mei_2025.json              # snapshot empresa + 12 meses
│   ├── sn_com_funcionarios_2025.json
│   ├── lp_2025.json
│   └── lr_2025.json
├── test_lancador_nf_saida.py
├── test_lancador_nf_entrada.py
├── test_lancador_transacao.py
├── test_lancador_depreciacao.py
├── test_lancador_provisao.py
├── test_lancador_folha.py
└── test_reconciliacao_fiscal.py
```

#### 3.1.2 Exemplo: NF Saída

```python
# tests/golden/contabil/test_lancador_nf_saida.py

import pytest
from datetime import date
from decimal import Decimal
from app.modules.contabil.lancador_auto import gerar_partidas_nf_saida

def test_nf_saida_simples_nacional():
    """
    NF saída SN: 1 serviço, R$1.000, ISS 5% retido.
    Esperado:
      D: Clientes 1.000
      C: Receita Serviços 1.000
    (ISS é retido depois, separadamente)
    """
    nf = NfFatoView(
        id=UUID("00000001-0000-0000-0000-000000000001"),
        tipo="nfse",
        direcao="saida",
        valor_total=Decimal("1000.00"),
        emitida_em=datetime(2025, 1, 15),
        numero="123",
    )
    
    contas = ContasAuto(
        clientes=UUID("clientes-uuid"),
        receita_servicos=UUID("receita-uuid"),
        # ... outros
    )
    
    partidas = gerar_partidas_nf_saida(nf, contas)
    
    assert len(partidas) == 2
    assert partidas[0].tipo == "D" and partidas[0].valor == Decimal("1000.00")
    assert partidas[1].tipo == "C" and partidas[1].valor == Decimal("1000.00")
    assert partidas[0].conta_id == contas.clientes

def test_nf_saida_com_desconto():
    """NF saída com desconto: contabiliza pelo valor líquido."""
    nf = NfFatoView(
        ...
        valor_total=Decimal("900.00"),  # 1.000 - 100 desc
    )
    partidas = gerar_partidas_nf_saida(nf, contas)
    assert partidas[0].valor == Decimal("900.00")

def test_nf_saida_diferenca_regional_icms():
    """NF saída SP→MG: diferença de ICMS (DIFAL) é lançada separadamente."""
    # SP: 12%, MG: 18% → diferença 6% fica em conta transitória
    pass

def test_nf_saida_para_consumidor_final():
    """NF saída para PF (sem CNPJ): sem duplicata, sem crédito."""
    nf = NfFatoView(
        ...
        cnpj_destinatario=None,  # PF
    )
    partidas = gerar_partidas_nf_saida(nf, contas)
    # Contabilização simplificada (sem risco de inadimplência)
    pass
```

#### 3.1.3 Exemplo: NF Entrada

```python
# tests/golden/contabil/test_lancador_nf_entrada.py

def test_nf_entrada_compra_revenda():
    """
    NF entrada CFOP 1.102 (compra revenda): vai para estoques.
    Valor R$500, ICMS 12% = R$60 crédito (recuperável SN/LP).
    """
    nf = NfFatoView(
        id=UUID("entrada-01"),
        tipo="nfe",
        direcao="entrada",
        valor_total=Decimal("500.00"),
        cfop="1.102",
        emitida_em=datetime(2025, 1, 20),
    )
    
    contas = ContasAuto(
        estoques=UUID("estoques-uuid"),
        fornecedores=UUID("fornec-uuid"),
    )
    
    partidas = gerar_partidas_nf_entrada(nf, contas, regime="simples_nacional")
    
    # Crédito ICMS não é recuperável em SN → debita tudo em estoques
    assert len(partidas) == 2
    assert partidas[0].tipo == "D" and partidas[0].conta_id == contas.estoques
    assert partidas[0].valor == Decimal("500.00")  # com ICMS agregado

def test_nf_entrada_bem_imobilizado():
    """
    NF entrada CFOP 1.556 (bem para ativo): vai para imobilizado.
    Microcomputador R$3.000.
    """
    nf = NfFatoView(
        ...
        cfop="1.556",
        valor_total=Decimal("3000.00"),
    )
    
    partidas = gerar_partidas_nf_entrada(nf, contas, regime="simples_nacional")
    
    assert partidas[0].conta_id == contas.imobilizado
    assert partidas[0].valor == Decimal("3000.00")

def test_nf_entrada_servico():
    """
    NF entrada CFOP 1.933 (comunicação): despesa.
    Telefone R$200.
    """
    nf = NfFatoView(
        ...
        cfop="1.933",
        valor_total=Decimal("200.00"),
    )
    
    partidas = gerar_partidas_nf_entrada(nf, contas)
    
    assert partidas[0].conta_id == contas.despesa_servicos
```

#### 3.1.4 Exemplo: Reconciliação Fiscal

```python
# tests/golden/contabil/test_reconciliacao_fiscal.py

def test_balancete_vs_apuracao_das():
    """
    Empresa SN, jan/2025:
    - Receita bruta: R$10k
    - DAS apurado: R$730 (faixa 2)
    
    Contabilidade:
    - Débito: Clientes 10.000
    - Crédito: Receita 10.000
    
    Balancete final:
    - Clientes: 10.000 (D)
    - Receita: 10.000 (C)
    - DAS a Pagar: 730 (C)
    
    Validação: soma receitas janeiro ≈ base de cálculo DAS
    """
    # Carrega snapshot empresa SN jan/2025
    # Calcula DAS via modulo fiscal
    das_calculado = Decimal("730.00")
    
    # Extrai soma de "Receita Serviços" + "Receita Vendas" do balancete
    balancete = await relatorios.balancete(empresa_id, date(2025, 1, 1))
    soma_receitas = sum(
        l.saldo for l in balancete
        if l.conta.descricao.startswith("Receita")
    )
    
    # Tolerância: 2% (arredondamentos)
    assert abs(soma_receitas - Decimal("10000.00")) < Decimal("200.00")

def test_balancete_vs_apuracao_lp():
    """
    Empresa LP, jan-mar 2025:
    - Lucro presumido IRPJ = R$50k × 8% = R$4k
    - Balancete deve ter lançamento "IRPJ a Recolher 4k"
    """
    pass

def test_balancete_vs_ecd_amarracoes():
    """
    Balancete dec/2025 exportado para ECD:
    - Todas as contas do balancete aparecem em I-01
    - Todas as contas com saldo aparecem em J-01
    - Soma J-01 (D-C) = 0
    """
    pass
```

---

### 3.2 Validação de Congruência — Detectar Erros Contábeis

**Objetivo:** Impedir lançamentos inválidos em tempo real.

#### 3.2.1 Validador: `app/modules/contabil/validador_congruencia.py`

```python
"""Validador de congruência contábil (Sprint 19)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

@dataclass
class ErroCongruencia:
    codigo: str
    descricao: str
    lancamento_id: str
    partida_index: int
    severidade: Literal["aviso", "erro"]


class ValidadorCongruencia:
    """Valida se lançamento bate com fatos geradores."""

    def validar_nf_saida(
        self,
        lancamento: LancamentoContabil,
        nf: DocumentoFiscal,
    ) -> list[ErroCongruencia]:
        """Valida se lançamento de NF saída está correto."""
        erros = []

        # Validação 1: se conta débito não é "Clientes", aviso
        partida_debito = next(
            (p for p in lancamento.partidas if p.tipo == "D"), None
        )
        if partida_debito and partida_debito.conta.descricao != "Clientes":
            erros.append(ErroCongruencia(
                codigo="CONGRUENCIA_001",
                descricao=f"NF saída deve debitar 'Clientes', não '{partida_debito.conta.descricao}'",
                lancamento_id=str(lancamento.id),
                partida_index=0,
                severidade="aviso",
            ))

        # Validação 2: se valor não bate com NF
        if partida_debito and partida_debito.valor != nf.valor_total:
            erros.append(ErroCongruencia(
                codigo="CONGRUENCIA_002",
                descricao=f"Valor lançamento R${partida_debito.valor} != NF R${nf.valor_total}",
                lancamento_id=str(lancamento.id),
                partida_index=0,
                severidade="erro",
            ))

        # Validação 3: se NF tem CFOP de entrada mas lançamento é como saída
        if nf.direcao == "entrada" and partida_debito and "Cliente" in partida_debito.conta.descricao:
            erros.append(ErroCongruencia(
                codigo="CONGRUENCIA_003",
                descricao="Lançamento é de entrada (fornecedor) mas debita conta de saída (cliente)",
                lancamento_id=str(lancamento.id),
                partida_index=0,
                severidade="erro",
            ))

        return erros

    def validar_nf_entrada(
        self,
        lancamento: LancamentoContabil,
        nf: DocumentoFiscal,
        regime: str,
    ) -> list[ErroCongruencia]:
        """Valida se lançamento de NF entrada está correto."""
        erros = []

        # Validação: CFOP deve mapear para conta correta
        conta_esperada = self._conta_esperada_por_cfop(nf.cfop, regime)
        partida_debito = next(
            (p for p in lancamento.partidas if p.tipo == "D"), None
        )

        if partida_debito and conta_esperada:
            if conta_esperada not in partida_debito.conta.codigo:
                erros.append(ErroCongruencia(
                    codigo="CONGRUENCIA_004",
                    descricao=f"CFOP {nf.cfop} deve debitar {conta_esperada}, não {partida_debito.conta.codigo}",
                    lancamento_id=str(lancamento.id),
                    partida_index=0,
                    severidade="aviso",
                ))

        return erros

    def _conta_esperada_por_cfop(self, cfop: str, regime: str) -> str | None:
        """Mapeia CFOP para conta esperada."""
        mapa = {
            "1.102": "1.1.02",  # Estoques
            "1.556": "1.2.01",  # Imobilizado
            "1.933": "5.1.02",  # Despesa Serviços
        }
        return mapa.get(cfop)
```

#### 3.2.2 Integração no Service

```python
# app/modules/contabil/service.py — adicionar

async def criar_lancamento_manual(
    self,
    session: AsyncSession,
    tenant_id: UUID,
    empresa_id: UUID,
    payload: CriarLancamentoIn,
) -> LancamentoOut:
    """Cria lançamento manual com validações."""
    
    # ... código existente ...

    # NOVO: validar congruência se há origem_id (lançamento de fato)
    if payload.origem_id:
        fato = await self._carregar_fato(session, payload.origem_tipo, payload.origem_id)
        if fato:
            validador = ValidadorCongruencia()
            erros = validador.validar_nf_saida(lancamento, fato)
            
            # Erros bloqueiam; avisos só logam
            erros_criticos = [e for e in erros if e.severidade == "erro"]
            if erros_criticos:
                raise LancamentoInvalido(
                    f"Lançamento inválido: {erros_criticos[0].descricao}"
                )
            
            for aviso in [e for e in erros if e.severidade == "aviso"]:
                log.warning("contabil.lancamento.aviso", aviso=aviso)

    await session.commit()
    return _lancamento_para_out(lancamento)
```

---

### 3.3 Performance em Escala — 10k+ Lançamentos/Mês

**Problema:** Balancete em <500ms mesmo com 10k lançamentos.

#### 3.3.1 Índices

```sql
-- Adicionar migration em alembic/versions/

-- Índice composto para consultas de período + empresa
CREATE INDEX ix_lancamento_empresa_competencia_status
  ON lancamento_contabil(empresa_id, competencia, status);

-- Índice para saldos
CREATE INDEX ix_saldo_conta_mes_empresa_competencia
  ON saldo_conta_mes(empresa_id, competencia);

-- Índice para partidas por conta
CREATE INDEX ix_partida_lancamento_conta
  ON partida_lancamento(conta_id, tipo);

-- Particionamento por ano (opcional, se >100k lançamentos/ano)
ALTER TABLE lancamento_contabil PARTITION BY RANGE (
  EXTRACT(YEAR FROM competencia)
);
```

#### 3.3.2 Materialized View de Balancete

```python
# Migration para criar view materializada

async def upgrade(op: Operations):
    op.execute("""
        CREATE MATERIALIZED VIEW balancete_mensal AS
        SELECT
            empresa_id,
            competencia,
            conta_id,
            SUM(CASE WHEN tipo='D' THEN valor ELSE 0 END) as total_debito,
            SUM(CASE WHEN tipo='C' THEN valor ELSE 0 END) as total_credito,
            SUM(CASE WHEN tipo='D' THEN valor ELSE -valor END) as saldo,
            MAX(updated_at) as atualizado_em
        FROM partida_lancamento pl
        JOIN lancamento_contabil lc ON pl.lancamento_id = lc.id
        WHERE lc.status IN ('confirmado', 'encerrado')
        GROUP BY empresa_id, competencia, conta_id;
    """)
    
    op.execute("""
        CREATE UNIQUE INDEX ix_balancete_mensal_pkey
        ON balancete_mensal(empresa_id, competencia, conta_id);
    """)
```

#### 3.3.3 Rebuild automático

```python
# app/workers/tasks/rebuild_balancete.py

from celery import shared_task

@shared_task(bind=True)
def rebuild_balancete_mensal(self, empresa_id: str, competencia: str):
    """Rebuild da view materializada — roda após encerramento."""
    with SessionLocal() as session:
        session.execute("""
            REFRESH MATERIALIZED VIEW CONCURRENTLY balancete_mensal
            WHERE empresa_id = :empresa_id
            AND competencia = :competencia
        """, {
            "empresa_id": empresa_id,
            "competencia": competencia,
        })
        session.commit()
```

#### 3.3.4 Cache Redis

```python
# app/modules/contabil/relatorios_service.py

class RelatoriosService:
    async def balancete(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        competencia: date,
    ) -> list[LinhaBalancete]:
        """Balancete com cache Redis (TTL 1h durante mês; invalida em novo lançamento)."""
        
        cache_key = f"balancete:{empresa_id}:{competencia.isoformat()}"
        
        # Tenta cache
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Se não está em cache, calcula
        linhas = await self._calcular_balancete(session, empresa_id, competencia)
        
        # Armazena em cache (TTL 1h)
        await redis_client.setex(
            cache_key,
            3600,
            json.dumps([l.dict() for l in linhas]),
        )
        
        return linhas

    async def invalidar_cache(self, empresa_id: UUID, competencia: date):
        """Invalida cache quando novo lançamento é criado."""
        cache_key = f"balancete:{empresa_id}:{competencia.isoformat()}"
        await redis_client.delete(cache_key)
```

---

### 3.4 Event-Driven — Workers Celery para Lançamentos Automáticos

**Objetivo:** Desacoplar geração de fatos de lançamentos; permitir retry + observabilidade.

#### 3.4.1 Eventos

```python
# app/shared/events.py

from dataclasses import dataclass
from uuid import UUID
from datetime import date

@dataclass
class DocumentoFiscalCriado:
    documento_id: UUID
    empresa_id: UUID
    tipo: str  # 'nfe' | 'nfse'
    direcao: str  # 'saida' | 'entrada'
    valor_total: Decimal
    timestamp: datetime

@dataclass
class TransacaoBancariaCriada:
    transacao_id: UUID
    empresa_id: UUID
    valor: Decimal
    tipo: str  # 'CREDIT' | 'DEBIT'
    timestamp: datetime

@dataclass
class DepreciacaoMensalCriada:
    depreciacao_id: UUID
    empresa_id: UUID
    competencia: date
    timestamp: datetime

# + Provisionamento, Folha, etc.
```

#### 3.4.2 Worker

```python
# app/workers/tasks/lancador_automatico.py

from celery import shared_task
from app.modules.contabil.lancador_auto import (
    gerar_partidas_nf_saida,
    gerar_partidas_nf_entrada,
    gerar_partidas_transacao,
)
from app.modules.contabil.repo import LancamentoRepo

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
)
def processar_documento_fiscal(self, evento: dict):
    """Worker que gera lançamento automático para NF."""
    evento_obj = DocumentoFiscalCriado(**evento)
    
    with SessionLocal() as session:
        try:
            # Carrega NF do BD
            nf = session.query(DocumentoFiscal).get(evento_obj.documento_id)
            if not nf:
                return
            
            # Carrega contas da empresa
            contas = await _carregar_contas_auto(session, evento_obj.empresa_id)
            
            # Gera partidas
            if nf.direcao == "saida":
                partidas = gerar_partidas_nf_saida(nf, contas)
            else:
                partidas = gerar_partidas_nf_entrada(nf, contas)
            
            # Persiste lançamento
            repo = LancamentoRepo(session)
            lancamento = await repo.criar(
                tenant_id=nf.tenant_id,
                empresa_id=evento_obj.empresa_id,
                data_lancamento=nf.emitida_em.date(),
                competencia=date(nf.emitida_em.year, nf.emitida_em.month, 1),
                historico=f"NF {nf.tipo.upper()} {nf.numero}",
                origem_tipo="documento_fiscal",
                origem_id=nf.id,
                status="confirmado",
                partidas=partidas,
            )
            
            log.info(
                "contabil.lancamento.automatico.criado",
                lancamento_id=str(lancamento.id),
                documento_id=str(nf.id),
            )
            
            # Invalida cache balancete
            await invalidar_cache_balancete(evento_obj.empresa_id, lancamento.competencia)
            
        except Exception as exc:
            log.error(
                "contabil.lancamento.automatico.erro",
                documento_id=str(evento_obj.documento_id),
                erro=str(exc),
            )
            raise self.retry(exc=exc)

@shared_task
def processar_transacao_bancaria(self, evento: dict):
    """Worker que gera lançamento para transação bancária."""
    # Similar
    pass

@shared_task
def processar_depreciacao(self, evento: dict):
    """Worker que gera lançamento para depreciação."""
    # Similar
    pass
```

#### 3.4.3 Event Publisher

```python
# app/modules/ingestao/service.py (exemplo: quando NF é ingerida)

class IngestaoService:
    async def persistir_documento_fiscal(
        self,
        session: AsyncSession,
        ...
    ):
        # ... salva DocumentoFiscal ...
        
        # Publica evento
        evento = DocumentoFiscalCriado(
            documento_id=novo_doc.id,
            empresa_id=novo_doc.empresa_id,
            tipo=novo_doc.tipo,
            direcao=novo_doc.direcao,
            valor_total=novo_doc.valor_total,
            timestamp=datetime.now(),
        )
        
        # Enfileira task
        from app.workers.celery_app import app
        app.send_task(
            "app.workers.tasks.lancador_automatico.processar_documento_fiscal",
            args=[evento.dict()],
            queue="lancador",
        )
```

---

### 3.5 Exportação e Validação de SPED no Dashboard

**UI:** Endpoints que permitam validar SPED antes de baixar.

```python
# app/modules/contabil/router.py — adicionar

@router.post("/sped/{arquivo_id}/validar")
async def validar_sped(
    arquivo_id: UUID,
    session = Depends(get_session),
) -> dict:
    """Valida SPED gerado contra critérios RFB."""
    
    arquivo = await ArquivoSPEDRepo(session).por_id(arquivo_id)
    if not arquivo:
        raise HTTPException(status_code=404)
    
    # Busca arquivo de S3
    arquivo_txt = await download_s3(arquivo.storage_key)
    
    # Valida
    validador = ValidadorSPED(arquivo_txt)
    erros = validador.validar()
    avisos = [e for e in erros if e.tipo == "aviso"]
    erros_criticos = [e for e in erros if e.tipo == "erro"]
    
    # Persiste resultado
    await ArquivoSPEDRepo(session).atualizar(
        arquivo_id,
        status="validado" if not erros_criticos else "rejeitado",
        validacao_jsonb={
            "erros": [e.dict() for e in erros_criticos],
            "avisos": [e.dict() for e in avisos],
        },
    )
    
    return {
        "status": "válido" if not erros_criticos else "inválido",
        "num_erros": len(erros_criticos),
        "num_avisos": len(avisos),
        "erros": [{"codigo": e.codigo, "descricao": e.descricao} for e in erros_criticos],
    }
```

---

## 4. Tier 3 — Nice-to-have (Sprint 21-22)

### 4.1 Consolidação Multi-Empresa

**Para escritórios contábeis com múltiplos clientes.**

```python
# app/modules/contabil/consolidacao.py

class ConsolidacaoService:
    """Consolida balancetes de múltiplas empresas."""
    
    async def balancete_consolidado(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresas_ids: list[UUID],
        competencia: date,
        eliminar_inter_empresa: bool = True,
    ) -> list[LinhaBalanceteConsolidado]:
        """Soma saldos de múltiplas empresas, eliminando transações inter-empresa."""
        
        # 1. Carrega balancete de cada empresa
        balancetes = []
        for empresa_id in empresas_ids:
            saldos = await self.balancete(session, empresa_id, competencia)
            balancetes.append((empresa_id, saldos))
        
        # 2. Consolida (soma por código de conta)
        saldos_consolidados = defaultdict(Decimal)
        for empresa_id, linhas in balancetes:
            for linha in linhas:
                saldos_consolidados[linha.conta.codigo] += linha.saldo
        
        # 3. Elimina inter-empresa (se flag)
        if eliminar_inter_empresa:
            # Busca lançamentos entre empresas do grupo
            inter_empresa = await self._buscar_lancamentos_inter_empresa(
                session, empresas_ids, competencia
            )
            for lance in inter_empresa:
                # Zera o débito/crédito
                pass
        
        return saldos_consolidados
```

---

### 4.2 Customização de Plano de Contas por Setor

**Para indústria, construção, saúde, etc.**

```python
# app/modules/contabil/planos_setoriais.py

PLANO_CONSTRUCAO_CIVIL = {
    "1.1.01": {"descricao": "Caixa", "nivel": 2},
    "1.1.02": {"descricao": "Banco CEI (obra)", "nivel": 2},  # conta adicional
    "1.2.01": {"descricao": "Imobilizado — Máquinas de obra", "nivel": 2},
    # ... customizações
}

PLANO_SAUDE = {
    # Contas específicas para clínicas (DMED, convênios, etc)
}
```

---

## 5. Golden Tests Obrigatórios

**Bloqueia merge em CI se algum falhar.**

### 5.1 Estrutura

```
tests/golden/contabil/
├── conftest.py                 # Fixtures empresas de teste
├── test_lancador_nf_saida.py   # 15+ casos
├── test_lancador_nf_entrada.py # 20+ casos (por CFOP)
├── test_lancador_transacao.py  # 10+ casos
├── test_lancador_depreciacao.py # 10+ casos
├── test_lancador_provisao.py   # 8+ casos
├── test_lancador_folha.py      # 8+ casos
├── test_partidas_validacao.py  # 15+ casos (partida dobrada)
├── test_encerramento_mensal.py # 8+ casos
├── test_encerramento_anual.py  # 5+ casos
├── test_relatorios_dre.py      # 10+ casos
├── test_relatorios_balancete.py # 10+ casos
├── test_reconciliacao_fiscal.py # 10+ casos
└── fixtures/
    ├── empresa_sn_mei_2025.json
    ├── empresa_sn_com_funcionarios_2025.json
    ├── empresa_lp_2025.json
    └── empresa_lr_2025.json
```

### 5.2 Padrão de Teste Golden

```python
# Cada teste segue este padrão:

def test_caso_descritivo():
    """
    Descrição técnica + esperado.
    
    Setup: empresa + período + documentos/transações
    Ação: gera lançamentos automáticos
    Validação: balancete final = esperado
    """
    # Load fixture
    empresa = load_fixture("empresa_sn_mei_2025.json")
    
    # Setup: cria NF saída jan/2025
    nf_saida = DocumentoFiscal(
        tipo="nfse",
        direcao="saida",
        numero="123",
        valor_total=Decimal("1000.00"),
        emitida_em=datetime(2025, 1, 15),
    )
    session.add(nf_saida)
    session.commit()
    
    # Action: gera lançamento automático
    svc = ContabilService()
    lancamento = await svc.gerar_lancamento_nf_saida(
        session, empresa.tenant_id, empresa.id, nf_saida.id
    )
    
    # Validate
    assert lancamento.status == "confirmado"
    assert len(lancamento.partidas) == 2
    assert lancamento.partidas[0].tipo == "D"
    assert lancamento.partidas[0].valor == Decimal("1000.00")
    assert lancamento.partidas[1].tipo == "C"
    assert lancamento.partidas[1].valor == Decimal("1000.00")
    
    # Balancete final
    balancete = await RelatoriosService().balancete(
        session, empresa.id, date(2025, 1, 1)
    )
    
    # Validação: clientes = 1.000 (D), receita = 1.000 (C)
    linha_clientes = next(
        l for l in balancete if "Clientes" in l.conta.descricao
    )
    assert linha_clientes.saldo == Decimal("1000.00")
```

---

## 6. Checklists de Implementação

### 6.1 Checklist Sprint 16 — ECD + ECF

- [ ] Criar `app/shared/sped/layouts.py` com definições de blocos 0, I, J, 9
- [ ] Implementar `app/shared/sped/ecd_generator.py`
  - [ ] Bloco 0 (abertura)
  - [ ] Bloco I (informações contábeis)
  - [ ] Bloco J (balancete e encerramento)
  - [ ] Bloco 9 (fechamento)
- [ ] Implementar `app/shared/sped/validators.py`
  - [ ] Validação estrutura blocos
  - [ ] Validação amarração balancete (soma D=C)
  - [ ] Testes unitários
- [ ] Implementar `app/shared/sped/ecf_generator.py` (similiar a ECD, com blocos fiscais)
- [ ] Criar migration `alembic/versions/XXX_arquivo_sped.py`
  - [ ] Tabela `arquivo_sped` (tipo, período, storage_key, status, etc)
  - [ ] Índices
- [ ] Criar schemas `ArquivoSPEDOut`, `ArquivoSPEDIn`
- [ ] Criar endpoints
  - [ ] `POST /api/v1/contabil/sped/ecd/{empresa_id}/{ano}/gerar`
  - [ ] `GET /api/v1/contabil/sped/ecd/{empresa_id}/{ano}/download`
  - [ ] `POST /api/v1/contabil/sped/{arquivo_id}/validar`
- [ ] Implementar upload/download S3
- [ ] Testes unitários: `tests/unit/contabil/test_ecd_generator.py`
- [ ] Testes golden: `tests/golden/contabil/test_sped_ecd.py`
  - [ ] Caso empresa SN janela fiscal completa
  - [ ] Caso empresa LP com trimestral
  - [ ] Validações críticas (balancete, amarrações)
- [ ] Documentar em ADR 0012 (geração SPED própria)

### 6.2 Checklist Sprint 17 — EFD-Contribuições + EFD ICMS-IPI

Similar ao Sprint 16, mas:
- [ ] `app/shared/sped/efd_contribuicoes.py`
  - [ ] Blocos A, B, C, E, F
  - [ ] Cálculo PIS 1.65% + Cofins 7.6% (LP/LR)
  - [ ] Reconciliação com DocumentoFiscal
- [ ] `app/shared/sped/efd_icms_ipi.py`
  - [ ] Blocos C, D, E, F, H
  - [ ] Múltiplas alíquotas por UF
  - [ ] DIFAL (inter-estadual)
- [ ] Testes golden: `tests/golden/contabil/test_efd_contribuicoes_golden.py`

### 6.3 Checklist Sprint 18 — Importador Histórico + Golden Tests

- [ ] Importador SPED 12 meses (para dados antigos)
  - [ ] Parser SPED antigo → estrutura interna
  - [ ] Reconstruir grafo histórico
- [ ] Importador CSV planilha
- [ ] Golden suite completa
  - [ ] 100+ casos em `tests/golden/contabil/`
  - [ ] Coverage >95% módulo contabil
- [ ] CI integration
  - [ ] Golden tests bloqueiam merge se falham

### 6.4 Checklist Sprint 19 — Validação + Performance + Event-Driven

- [ ] `app/modules/contabil/validador_congruencia.py`
  - [ ] Validação NF saída ↔ lançamento
  - [ ] Validação NF entrada ↔ CFOP
  - [ ] Testes
- [ ] Índices
  - [ ] Migration `ix_lancamento_empresa_competencia_status`
  - [ ] Materialized view `balancete_mensal`
- [ ] Cache Redis
  - [ ] Implementar em `RelatoriosService.balancete()`
  - [ ] Invalidação automática em novo lançamento
- [ ] Event-driven
  - [ ] `app/shared/events.py` (event dataclasses)
  - [ ] `app/workers/tasks/lancador_automatico.py` (workers Celery)
  - [ ] Integrar publisher em serviços geradores (ingestão, pessoal, etc)
  - [ ] Testes de retry, observabilidade (Langfuse)

### 6.5 Checklist Sprint 20 — Polish Lucro Presumido

- [ ] Validação end-to-end com 10 empresas LP piloto
- [ ] Ajustes SPED ECD/ECF conforme feedback
- [ ] Performance tunning final
- [ ] Documentação OpenAPI completa

---

## 7. Estimativas e Dependências

### Timeline

| Sprint | Tema | Semanas | Dependência |
|--------|------|---------|-------------|
| 16 | ECD + ECF | 2 | Nenhuma |
| 17 | EFD-Contrib + EFD ICMS-IPI | 2 | Sprint 16 (espaçar em 2 semanas) |
| 18 | Importador + Golden tests | 2 | Sprint 16-17 |
| 19 | Validação + Perf + Event | 2 | Sprint 18 |
| 20 | Polish LP | 2 | Sprint 19 |

**Total:** 10 semanas (5 sprints de 2 semanas cada)

### Recursos

- **1 Senior Backend** (100%) — arquitetura SPED, validadores, testes
- **1 Mid Backend** (100%) — workers, performance, event-driven
- **1 QA/Tester** (50%) — golden tests, casos edge, integração

---

## 8. Referências Legais

| Norma | Escopo | Versão |
|-------|--------|--------|
| **Ato COTEPE/ICMS 9/2008** | Leiaute ECD | Vigente |
| **IN RFB 2.004/2021** | Leiaute ECF | Vigente |
| **IN RFB 1.488/2014** | Leiaute EFD-Contrib | Vigente |
| **Ato COTEPE/ICMS 67/2000** | Leiaute EFD ICMS-IPI | Vigente |
| **IN SRF 162/1998** | Depreciação | Vigente (tabelas ajustadas anualmente) |
| **LC 123/2006** | Simples Nacional | Vigente |
| **IN RFB 1.700/2017** | Lucro Presumido | Vigente |

Todos os layouts são **versionados anualmente pela RFB** via Ato COTEPE/ICMS. Antes de cada merge, validar versão vigente.

---

## 9. Perguntas Frequentes

**P: Por que não usamos biblioteca pronta (Sage, Domínio)?**  
R: Princípio §8.12 — transmissão é ato consciente do cliente. Bibliotecas prontas transmitem automaticamente; nossa geração deixa o cliente escolher. Além disso, customizabilidade futura (verticais, validações customizadas).

**P: Qual é a tolerância de erro em validação SPED?**  
R: ZERO para erros críticos (balancete desbalanceado, DNCs inválidos). Avisos só logam.

**P: Posso ignorar EFD se a empresa só faz Simples Nacional?**  
R: Sim. EFD-Contrib é obrigatória LP+. EFD ICMS-IPI depende do município. Validar obrigatoriedade por CNAE + município da empresa.

**P: Como versionar algoritmos se mudar fórmula de lançamento?**  
R: Toda mudança incrementa `ALGORITMO_VERSAO`. Lançamentos históricos ficam com versão original. Recalculação é manual (Sprint 18+).

---

## 10. Próximos Passos Imediatos

1. **Hoje:** Revisar este documento com time
2. **Amanhã:** Criar epic no backlog (22 user stories)
3. **Sprint 16 semana 1:** Setup `app/shared/sped/`, criar Migration, fixtures
4. **Sprint 16 semana 2:** Gerador ECD, validador, testes

---

**Documento vivo.** Atualizar conforme implementação avança.  
Versão: 1.0 | Data: 2026-06-05
