# 🧾 AUTO DE INFRAÇÃO FISCAL — Arkan / Analista Fiscal
**Data:** 2026-06-21 · **Vigência de referência verificada:** jun/2026 · **Auditor-Chefe:** Claude Opus 4.8
**Veredicto:** 🔴 **REPROVADO PARA PRODUÇÃO** — 2 erros fiscais ativos desde 01/01/2026 que fazem o cliente pagar/reter errado HOJE, mais 5 críticos de reconciliação/apuração.

---

## RESUMO DO AUDITOR

A espinha dorsal é boa: INSS 2026 seedado e correto (teto R$ 8.475,55), SCD Type 2 em todas as 9 tabelas tributárias com trigger fechando vigência, Decimal/ROUND_HALF_EVEN disciplinado, golden tests fartos, idempotência na emissão de NF, sem dependência da Nuvem Fiscal. **Mas o sistema calcula bonito e erra em silêncio em dois pontos que doem AGORA:** o **IRRF roda a tabela de fev/2024** — ignora o redutor da Lei 15.270/2025 e cobra imposto a maior de quem ganha até R$ 7.350 desde janeiro; e a **distribuição de lucros não retém os 10% na fonte** sobre o que excede R$ 50.000/mês (Lei 15.270/2025, inclusive Simples). Ambos confirmados na web contra a lei vigente.

Além disso: o **Fator R do Simples é calculado sem encargos** (subtributa quem deveria estar no Anexo III, joga para o V) e o **PGDAS transmite a folha vazia** ao SERPRO — duas faces do mesmo erro que muda o valor do DAS. Na contabilidade, a **DRE conta IRPJ/CSLL duas vezes** e o **lançador automático persiste sem validar partida dobrada**. Na ingestão, a **reconciliação ICMSTot × soma dos itens é prometida na docstring mas não existe**. No calendário, o **FGTS vence no dia 7** (a lei mandou dia 20 desde o FGTS Digital). Encontrei **33 minúcias** — listadas integralmente. **Não vai para produção assim.**

---

## PLACAR

| Severidade | Qtd |
|---|---|
| 🔴 Crítico | 7 |
| 🟠 Grave | 8 |
| 🟡 Moderado | 7 |
| 🔵 Minúcia | 33 |

---

## ACHADOS POR AUDITOR

### A1 — Apuração · Veredicto: RESSALVAS GRAVES
**Módulos:** fiscal, lucro_presumido, icms, pgdas, multa_juros, declaracao_anual

| Sev | Arquivo:linha | Achado | Fonte legal | Esperado vs. Encontrado |
|---|---|---|---|---|
| 🔴 | `fiscal/service.py:106` | **Fator R sem encargos** — `fator_r = folha_12m / rbt12`; o numerador não soma CPP/FGTS/13º. Subestima o Fator R → empresa que deveria cair no Anexo III (≥28%) é jogada no Anexo V (alíquota maior). Imposto a MAIOR contra o cliente. | LC 123/2006 art. 18 §5º-J e §24; Res. CGSN 140/2018 art. 26 §1º | `(folha + encargos)/rbt12` vs `folha_12m/rbt12` |
| 🔴 | `pgdas/service.py:285-298` | **PGDAS-D transmite `folhasSalario: []` sempre vazio**, mesmo p/ Anexo III/V. O SERPRO recalcula o Fator R da folha do payload → folha vazia → resolve Anexo V → DAS divergente do calculado internamente (Anexo III). Quebra de reconciliação. | LC 123/2006 art. 18 §5º-J; Manual PGDAS-D | folha 12m discriminada vs `"folhasSalario": []` |
| 🟠 | `fiscal/calcula_das.py:160-163` | **Início de atividade sem proporcionalização do RBT12** — empresa nova (RBT12=0) usa alíquota nominal da faixa 1. A lei manda `RBT12 = (receita acumulada/nº meses)×12`. Subtributa quem já passa da faixa 1 no 1º mês. | Res. CGSN 140/2018 art. 18 §§2º-3º | média×12 → faixa correta vs RBT12=0 → faixa 1 nominal |
| 🟡 | `icms/calcula_icms.py:181` | `aliquota_efetiva` decorativa — soma interna+fecp mas não reconcilia com `icms_a_recolher`; FECP do RJ não entra no saldo apurado dentro da função. | Lei estadual RJ 4.056/2002 | efetiva consistente com o apurado vs campo desacoplado |

**Verificações POSITIVAS (sem achado):** Fator R borda 28,00% exato usa `>=` com golden (`calcula_das.py:88-96`); multa de mora 0,33%/dia teto 20% com golden de borda 60d/61d; denúncia espontânea zera multa e mantém SELIC (CTN 138); adicional IRPJ na borda R$60.000/trimestre coberto; presunção LP e bases CSLL≠IRPJ corretas; PIS/COFINS cumulativos 0,65%/3% corretos.
**Sem fonte:** nenhuma material. **Sem golden de borda:** proporcionalização do 1º mês (testa o comportamento incorreto); Fator R montando `(folha+encargos)`; reconciliação PGDAS×DAS.

---

### A2 — Folha & eSocial · Veredicto: 🔴 REPROVADO
**Módulos:** pessoal, provisoes

| Sev | Arquivo:linha | Achado | Fonte legal | Esperado vs. Encontrado |
|---|---|---|---|---|
| 🔴 | `pessoal/calcula_irrf.py` (todo) + `alembic/0016_…_pessoal_tabelas.py:435-462` | **IRRF não modela o redutor da Lei 15.270/2025.** A tabela `tabela_irrf_faixa` só tem vigência 2024 (`valid_from=2024-02-01, valid_to=NULL`) — nenhuma vigência 2026. Cobra IRRF a maior na base da pirâmide desde 01/2026. **Confirmado na web.** | Lei 15.270/2025 (vig. 01/01/2026): isenção efetiva até R$ 5.000; redução gradual até R$ 7.350 (`978,62 − 0,133145×rend.`) | IRRF≈0 até R$5.000 vs tabela 2024 sem redutor |
| 🔴 | `pessoal/calcula_distribuicao.py:73-140` | **Distribuição de lucros sem retenção de 10% na fonte.** Só trata isenção + IRRF progressivo no excedente contábil. Sem campo, sem cálculo, sem IRPFM. **Confirmado na web (inclusive Simples).** | Lei 15.270/2025: 10% sobre lucros/dividendos mesma PJ→PF que excedam R$ 50.000/mês ("superior a" → 50.000 exato não retém) | 10% acima de R$50k/mês vs zero retenção |
| 🔵 | `tests/unit/pessoal/test_calcula_distribuicao.py:41-50` | Golden de R$100.000 esperando 0 retenção fixa o comportamento errado como "ouro". Falta borda R$ 50.000,01. | Lei 15.270/2025 | — |
| 🔵 | `pessoal/calcula_irrf.py:46` | `ALGORITMO_VERSAO="irrf.mensal.v2"` e docstring citam Lei 14.848/2024 — defasará quando o redutor 2026 entrar. | Lei 15.270/2025 | — |
| 🔵 | `alembic/0058_inss_2026_nova_vigencia.py:23` | Comentário descreve faixa 4 como "teto"; a faixa 4 é intervalo (4.354,28→8.475,55). Valor seedado correto. | Portaria MPS/MF 13/2026 | — |

**Verificações POSITIVAS:** INSS 2026 (teto R$ 8.475,55, faixas 7,5/9/12/14%) seedado e correto com SCD; pró-labore usa 11% plano (não progressiva); 13º/férias com 1/3 constitucional e IRRF separado; rescisão com todas as verbas (aviso Lei 12.506/2011, multa FGTS 40%); FGTS 8%; eventos eSocial S-1200/S-2200/S-2299/S-2300/S-3000 corretos; provisões reconciliam (≤ R$0,01).

---

### A3 — Documentos Fiscais · Veredicto: 🔴 REPROVADO
**Módulos:** notas, ingestao, contabil/classificador_cfop, contabil/classificacao_ncm

| Sev | Arquivo:linha | Achado | Fonte legal | Esperado vs. Encontrado |
|---|---|---|---|---|
| 🔴 | `ingestao/parser.py:71-73` vs `277-399` | **Docstring promete reconciliação ICMSTot × soma dos itens (tolerância R$0,02) que NÃO EXISTE na função.** Não há `sum()` dos itens nem comparação com `vNF`. NF inconsistente entra como "autorizada". Docstring mentirosa. | MOC NF-e / Layout 4.00 (vNF = Σ vProd − desc + acr) | somar itens e rejeitar divergência >R$0,02 vs nenhuma conferência |
| 🟠 | `ingestao/parser.py:178-274` + `service.py:54-95` | **Sem validação CST × CSOSN vs regime (CRT).** `_parse_item` aceita CST ou CSOSN indistintamente em `cst_icms`; nunca cruza com o CRT. Simples (CRT 1) deve usar CSOSN; Normal (CRT 3) deve usar CST. | Anexo CRT; tabela CST × CSOSN (Ajuste SINIEF) | CRT 1/2⇒CSOSN, 3⇒CST vs nenhuma checagem |
| 🟠 | `ingestao/parser.py:351-354` | **CFOP/NCM do cabeçalho lidos sem a validação de formato** que `_parse_item` aplica (isdigit/len). Persiste CFOP/NCM possivelmente malformado; NCM inexistente não é detectada. | NCM 8 díg. (NESH/SH); CFOP 4 díg. (Convênio s/nº 1970) | mesma validação do item vs cabeçalho aceita qualquer string |
| 🟡 | `notas/service.py:188` + `schemas.py:100` | `mensagem_sefaz` repassada **literal** ao usuário (código + jargão sem tradução). | Regra do projeto: não expor jargão fiscal cru | traduzir vs passthrough cru |
| 🟡 | `ingestao/router.py:39-46` | `XmlInvalido(str(exc))` propaga mensagem técnica do parser ao dono de PME. | Regra do projeto | mensagem amigável vs detalhe interno |
| 🔵 | `ingestao/parser.py:332-336` | `_decimal()` silencia `InvalidOperation` → `Decimal("0")`. Total ilegível vira R$0,00 sem alarme. | Disciplina 4/5 | rejeitar vs degradar a 0,00 |
| 🔵 | `ingestao/parser.py:265` | `quantidade if >0 else Decimal("1")` — quantidade zero "consertada" para 1, distorce valor unitário. | Layout NF-e (qCom) | preservar/sinalizar vs inventar 1 |
| 🔵 | `contabil/classificador_cfop.py:34-50` | Mapa CFOP sem entrada 3.xxx (importação/exterior) — caem em `outras_despesas`. | Convênio s/nº 1970 | tratar 3.xxx vs silêncio no fallback |
| 🔵 | `contabil/classificacao_ncm.py:66-105` | Capítulo NCM heurístico sem citação de vigência (NESH/SH/TIPI). | Disciplina 2 | amarrar à versão datada vs mapa solto |
| 🔵 | `notas/schemas.py:19-25` | `natureza_operacao: Literal[1,2]` é enum legado da Focus, não o leiaute ADN nacional (vigente desde 01/2026). | NT/ADN NFS-e 2026 | alinhar ao ADN vs enum de 2 valores |
| 🔵 | `ingestao/service.py:96-97` | Cabeçalho usa CFOP/NCM **do 1º item** como representativo; NF multi-CFOP fica enviesada e o lançador classifica a nota inteira pelo item 1. | Classificação correta da despesa | classificar por item vs herdar item 1 |

**Verificações POSITIVAS:** sem dependência de Nuvem Fiscal (só Focus); idempotência via `uuid5(empresa_id, numero_rps)` com golden; DANFSe delegado ao emissor (compatível com NT 008/2026); alíquotas ISS com fonte (LC 116/2003).

---

### A4 — Escrituração & SPED · Veredicto: RESSALVAS GRAVES
**Módulos:** contabil, relatorios, sped, conciliacao, imobilizado

| Sev | Arquivo:linha | Achado | Fonte legal | Esperado vs. Encontrado |
|---|---|---|---|---|
| 🔴 | `relatorios/calcula_dre.py:244-252` | **"Outras Despesas Operacionais" captura 5.2 (Financeiras) e 5.3 (Provisão IRPJ/CSLL) dentro do EBITDA/EBIT.** Resultado financeiro deveria entrar só após o EBIT e IRPJ/CSLL só via `irpj_csll_apurado` → **dupla contagem** do IRPJ/CSLL e do financeiro. | Lei 6.404/76 art. 187 | EBIT só operacional vs 5.2/5.3 inflando Outras Despesas |
| 🔴 | `contabil/lancador_service.py:593-633` | **Lançador automático persiste sem validar partida dobrada.** `_persistir` grava `total_debito=total_credito=candidato.total` sem rodar `validar_partidas` nem comparar Σ-D×Σ-C nem rejeitar valor 0. Folha com líquido negativo gravaria "C" negativo; folha sem IRRF grava partida valor=0. | §8.4 + partida dobrada (Lei 6.404 art. 177) | persistir só se Σ-D==Σ-C e valor>0 vs confia no conversor |
| 🟠 | `imobilizado/service.py:106-107` | `_resolver_taxa_vida_util` aceita taxa **e** vida útil sem checar coerência; o algoritmo usa só `vida_util_meses`, e `taxa_depreciacao_anual` é persistida mas nunca reconciliada (ficha × cálculo divergem). | IN SRF 162/1998 | validar taxa ≈ 12/vida vs convivem em silêncio |
| 🟡 | `contabil/encerramento_service.py:288-294` | Encerramento anual não segrega financeiro/IRPJ — herda a falta de fronteira da DRE; sem golden cruzando "resultado do encerramento" == "lucro líquido da DRE". | Lei 6.404/76 art. 187/189 | golden de reconciliação vs inexistente |
| 🔵 | `imobilizado/calcula_depreciacao.py:9-12` | Pro-rata-die não implementado; bem adquirido dia 1º perde 1 mês. Decisão consciente, sem golden. | IN SRF 162/1998 art. 305 | — |
| 🔵 | `contabil/plano_referencial.py:413` | Sintética "5 DESPESAS" → `codigo_ecd_referencial="4.99"`, mas filhas mapeiam "4.02/4.03/4.05" — pai ECD não é ancestral. Sem impacto no arquivo (I051 só analíticas). | Plano Referencial RFB (ECD) | — |
| 🔵 | `conciliacao/algoritmo.py:121-134` | Faixa de valor R$5–R$50 não pontua valor mas segue pontuando data/CNPJ — conferir se deveria penalizar. | Regra de negócio | — |
| 🔵 | `contabil/lancador_auto.py:251` | NF entrada com CFOP de imobilizado (1.551/2.551) não tem golden cobrindo destino correto (1.2.3.01, não despesa). | Pendência consciente #5 | — |

**Verificações POSITIVAS:** taxas de depreciação batem com a IN 162/1998 (20/20/10/10/4%), início no mês seguinte; partida dobrada validada no lançamento **manual**; balanço/DFC com invariante de fechamento; SPED com leiautes/prazos corretos (ECD ADE Cofis 64/2024, ECF 51/2024).

---

### A5 — Vigências & Tabelas · Veredicto: RESSALVAS (1 🔴 = IRRF, já contado em A2; 1 🟠)
**Módulos:** tabelas_admin + transversal

| Sev | Arquivo:linha | Achado | Fonte legal | Esperado vs. Encontrado |
|---|---|---|---|---|
| 🔴 | `alembic/0016_…:435-464` + `calcula_irrf.py` | **IRRF vigente em 2026 é o de fev/2024** (mesma raiz do 🔴 de A2 — não recontar no placar). Vigência única 2024→NULL, isenção só até R$ 2.259,20, sem redutor. | Lei 15.270/2025 | nova vigência 2026 com redutor vs tabela 2024 ativa |
| 🟠 | `alembic/0055_fa7_icms_rj_fecp.py:57-70` | **UPDATE em linha de alíquota seedada e vigente** — `UPDATE aliquota_icms_uf SET aliquota_interna=0.18 WHERE uf='RJ' … valid_to IS NULL`. Reescreve o histórico: apuração retroativa de RJ jan–nov/2025 passa a ler 18% onde era 20%. Docstring contraditória ("nova vigência por UPDATE"). | §8.3 (nova vigência é INSERT, trigger fecha a anterior) | INSERT de nova vigência vs UPDATE direto |
| 🔵 | `alembic/0054_…:92-113` | UPDATE em `aliquota_cbs_ibs` só sela `valid_to` (não altera valor) — tolerável, citado por completude. | §8.3 | OK |
| 🔵 | `tabelas_admin/salario_minimo.py:32-41` | `dict[int,Decimal]` de SM histórico (2022–2026) hardcoded em .py de produção (reference-only, valor 2026 correto). Vigiar para não divergir do seed. | Decreto 12.797/2025 | — |
| 🔵 | `tabelas_admin/recheck_llm.py:165-189` | Re-check determinístico do LLM **não bloqueia** a criação da sugestão (só sinaliza); admin pode aprovar com re-check reprovado. | §8.6 | re-check impeditivo vs informativo |
| 🔵 | `alembic/0025/0034` | `conta_contabil` (SCD por empresa) sem trigger SCD nem REVOKE — fechamento de `valid_to` depende do service (tabelas tributárias públicas estão cobertas). | §8.3 | — |

**Resumo conferido contra o gabarito:** INSS teto 8.475,55 ✅ · SM 1.621,00 ✅ · Simples teto 4,8mi/sublimite 3,6mi ✅ · presunção LP 8/32/16/1,6% ✅ · depreciação 20/20/10/10/4% ✅ · FGTS 8% ✅ · **IRRF redutor ❌ (não implementado).** Único valor fiscal divergente da lei vigente: o IRRF. **Hardcode de tabela de faixas: limpo** (tudo no banco via SCD).

---

### A6 — Compliance & Prazos · Veredicto: REPROVADO COM RESSALVAS
**Módulos:** certidoes, e_cac, det, reinf, monitor_cadastral, parcelamentos, agenda

| Sev | Arquivo:linha | Achado | Fonte legal | Esperado vs. Encontrado |
|---|---|---|---|---|
| 🟠 | `agenda/gerar_calendario.py:243-250` | **FGTS gerado no dia 7** do mês seguinte; cita "Lei 8.036/1990 art.15 §5º" (texto revogado) e ignora a Lei 14.438/2022. Afeta SN e LP → 24 itens FGTS/ano com data errada. **Confirmado na web: vence dia 20 (FGTS Digital, comp. desde mar/2024), e em dia não-útil ANTECIPA.** | Lei 14.438/2022 (dia 7→20); FGTS Digital | dia 20 (antecipa em dia não-útil) vs dia 7 |
| 🟠 | `parcelamentos/calcula_parcelamento.py:154-164` | Vencimento de parcela **não posterga p/ dia útil** (só corrige dia inexistente). Diverge do tratamento da agenda. | IN RFB 2.063/2022 + regra geral | postergar p/ dia útil vs data crua |
| 🟡 | `parcelamentos/calcula_parcelamento.py:17-27` | Parcela = `dívida/n` **sem SELIC acumulada + 1%**. Out-of-scope declarado, mas o valor mostrado ao cliente subestima a parcela real. | Lei 10.522/2002 art.12; IN 2.063/2022 | parcela corrigida vs nominal |
| 🟡 | `e_cac/service.py:107-121` | Resumo de intimação por **IA com citação** prometido na docstring, mas a classificação é só keyword — funcionalidade-chave não existe. | §8.5 | resumo IA citado vs regex |
| 🔵 | `e_cac/classificador.py:141-148` | `_extrair_prazo` usa `date.today()` **dentro da função pura** — viola pureza/reprodutibilidade. | §8.2 | base na `recebida_em` vs `date.today()` |
| 🔵 | `e_cac/classificador.py:128-149` | Prazo extraído é data corrida, sem postergar p/ dia útil nem antecedência de alerta. | Decreto 70.235/1972 art.5º | — |
| 🔵 | `certidoes/service.py:52-56` | CND com **180 dias fixo** — ignora o campo `validade` retornado pelo SERPRO; pode divergir da data impressa. | Portaria Conj. RFB/PGFN 1.751/2014 art.10 | usar validade do SERPRO vs hoje+180 |
| 🔵 | `certidoes/service.py:54` | CRF (FGTS) 30 dias sem fonte normativa (só "Manual FGTS"). | Resolução Cons. Curador FGTS | citar norma vs comentário genérico |
| 🔵 | `reinf/calcula_retencao.py` | EFD-Reinf modela só IRRF 1,5% + CSRF 4,65%; **retenção previdenciária 11% (INSS) sobre cessão de mão de obra (R-2010)** tem enum mas não tem cálculo. | Lei 8.212/1991 art.31; R-2010 | cálculo R-2010 vs ausente |
| 🔵 | `reinf/calcula_retencao.py:13-14` | Comentário do limite CSRF (R$10) com justificativa histórica incoerente. Valor correto. | IN RFB 1.234/2012 | — |
| 🔵 | `certidoes/service.py:323-330` | Semântica de certidão **correta** (negativa=ok), mas o fallback default `EMITIDA` numa positiva mal-parseada mascara débito. | — | fallback conservador vs `emitida` neutro |
| 🔵 | `det/service.py` + `monitor_cadastral/service.py` | Sem golden test (CRUD/snapshot); DET não calcula prazo da intimação trabalhista. | — | — |

**Verificações POSITIVAS:** semântica de certidão correta (negativa=ok, positiva=problema, CE-PEN) — **sem inversão**; prazos da agenda corretos (DAS/PGDAS dia 20, eSocial/DCTFWeb dia 15, DEFIS 31/03, DASN-SIMEI 31/05) com postergação p/ dia útil e golden (Tiradentes, Natal).

---

### A7 — Reforma · Veredicto: APROVADO COM RESSALVAS
**Módulo:** reforma

| Sev | Arquivo:linha | Achado | Fonte legal | Esperado vs. Encontrado |
|---|---|---|---|---|
| 🟠 | `alembic/0034_…:147-162` + `reforma/repo.py:61-67` | **Simples Nacional recebe CBS/IBS informacional em 2026.** A vigência 2026 com `regime=None` casa para qualquer regime; nada exclui o SN. | LC 214/2025 art.41-42 + Res. CGSN — SN só destaca a partir de 2027 | SN sem CBS/IBS em 2026 vs SN recebe 0,9%/0,1% |
| 🟠 | `reforma/service.py:156-200` | Backfill `recalcular_historico_documentos` grava `valor_cbs/valor_ibs` em **toda** empresa, inclusive SN, sem checar `regime_tributario` (`valor_impostos` não é afetado ✅). | idem | pular/zerar SN vs escreve destaque em SN |
| 🟡 | `reforma/integrar_documento.py:99-104` | Base informacional = `valor_total` (vNF); o próprio comentário admite que a base oficial excluiria CBS/IBS "por dentro". Sem flag distinguindo aproximação. | LC 214/2025 art.12-13 | marca de aproximação vs observação genérica |
| 🔵 | `reforma/calcula_cbs_ibs.py:36` | `algoritmo_versao` "reforma.cbs-ibs.v1" duplicado em 3 lugares — risco de drift. | — | 1 fonte vs 3 literais |
| 🔵 | `alembic/0034:169-171` | Vigência 2027 já traz `aliquota_cbs=0.0880` (valor preliminar); conferir que 0054 fecha a cadeia. | LC 214/2025 art.349 | vigilância |
| 🔵 | `reforma/periodo_transicao.py:8-9` | Docstring omite que a dispensa de recolhimento em 2026 é condicionada ao cumprimento das obrigações acessórias (§3º). | LC 214/2025 art.348 §3º | — |
| 🔵 | `reforma/calcula_cbs_ibs.py:48-61` | Sem flag booleana `informacional` no resultado — natureza inferida só pelo enum de fase. | §8.12 | flag explícita vs inferência |
| 🔵 | módulo | PF contribuinte de IBS/CBS (inscrição CNPJ jul/2026) não tratado (não quebra). | LC 214/2025 | — |

**Verificações POSITIVAS:** alíquotas 2026 são `0.0090`/`0.0010` (não 0.9/0.1) com golden; o total da nota **não** soma CBS/IBS; **nenhum recolhimento** gerado em 2026; split payment só projeção 2027; toda saída carrega `observacao_estimativa`.

---

## RECONCILIAÇÃO CRUZADA (Auditor-Chefe)

O erro mais perigoso é o de fronteira: cada módulo "passa" sozinho, mas o sistema erra no encontro.

| Cruzamento | Achado de fronteira |
|---|---|
| **A2 ↔ A5 (IRRF)** | Mesmo defeito por dois ângulos: a tabela IRRF de 2024 ativa (A5) **é** a causa do IRRF sem redutor (A2). **Um achado, não dois** — deduplicado no placar (7 🔴, não 8). |
| **A1 ↔ A2 (Fator R)** | Triângulo do Fator R: A1 calcula `folha/rbt12` **sem encargos** (`fiscal/service.py:106`) e ainda transmite **folha vazia** ao SERPRO (`pgdas/service.py:285`). O conceito de "massa salarial" é do domínio de A2 (salários **+ CPP + FGTS + 13º**). Os três pontos têm de usar a MESMA definição de folha — hoje divergem entre si e do SERPRO. É a virada Anexo III↔V que faz o cliente pagar errado. |
| **A1 ↔ A4 (imposto → razão)** | O DAS/DARF apurado (A1) é lançado pelo lançador automático que **não valida partida dobrada** (A4, `lancador_service.py:593`). Se o valor apurado estiver certo mas a conversão p/ partidas tiver erro, ninguém percebe — não há trava nem golden cruzando "imposto apurado" == "imposto lançado". |
| **A3 ↔ A1 (nota → receita)** | A receita que a apuração soma vem das notas, mas a ingestão **não reconcilia ICMSTot × itens** (A3, `parser.py:71`). NF inconsistente entra como autorizada e pode contaminar a base da apuração. **Lacuna aberta:** não há prova de que nota cancelada/substituída sai da soma da receita — verificar. |
| **A2 ↔ A4 (folha → razão)** | O lançador automático pode gravar a folha com líquido negativo / partida valor=0 (A4) — ou seja, o total da folha (A2) que vira lançamento **não é conferido centavo a centavo** no caminho automático. |
| **A7 ↔ A3 (Reforma → DFe)** | O CBS/IBS que A7 calcula é gravado **inclusive em documentos de Simples Nacional** (A7 🟠) — exatamente o regime que A3 emite e que não deveria ter destaque em 2026. |
| **A6 ↔ A6 (FGTS dia não-útil)** | Mesmo corrigindo o FGTS para dia 20, o tratamento de dia não-útil do FGTS é **antecipação** (confirmado na web), não a postergação que `_proximo_dia_util` da agenda aplica. A correção precisa cobrir a direção, não só o número do dia. |

---

## TOP 10 — corrigir nesta ordem

| # | Sev | Achado | Arquivo | Por que dói |
|---|---|---|---|---|
| 1 | 🔴 | IRRF sem o redutor da Lei 15.270/2025 | `calcula_irrf.py` + `0016` (nova vigência 2026) | Cobra IR a maior de **toda** folha até R$7.350 desde jan/2026 — milhões de holerites errados, agora |
| 2 | 🔴 | Distribuição sem retenção de 10% | `calcula_distribuicao.py:73` | Cada dividendo >R$50k/mês não retido = recolhimento a menor; autuação na DAA |
| 3 | 🔴 | Fator R sem encargos | `fiscal/service.py:106` | Joga serviço do Anexo III p/ o V — DAS a maior contra o cliente |
| 4 | 🔴 | PGDAS transmite folha vazia | `pgdas/service.py:285` | DAS transmitido diverge do calculado — declaração inconsistente no SERPRO |
| 5 | 🔴 | DRE conta IRPJ/CSLL duas vezes | `relatorios/calcula_dre.py:244` | EBITDA/EBIT e lucro líquido errados sempre que houver saldo em 5.2/5.3 |
| 6 | 🔴 | Lançador automático sem validar partida dobrada | `lancador_service.py:593` | Balancete pode não fechar silenciosamente; folha negativa/valor 0 entra no razão |
| 7 | 🟠 | FGTS no dia 7 (lei: dia 20) | `agenda/gerar_calendario.py:243` | Avisa o prazo errado em 24 itens/ano p/ todo cliente com funcionário |
| 8 | 🔴 | Reconciliação ICMSTot × itens inexistente (docstring mente) | `ingestao/parser.py:71` | NF inconsistente entra como autorizada e contamina a apuração |
| 9 | 🟠 | Simples recebe CBS/IBS em 2026 | `reforma/repo.py:61` + `service.py:156` | Aplica a Reforma a quem a lei exclui até 2027 |
| 10 | 🟠 | UPDATE em alíquota ICMS RJ seedada | `alembic/0055:57` | Reescreve o histórico — apuração retroativa de RJ/2025 passa a ler 18% |

---

## CATÁLOGO DE MINÚCIAS (lista completa — 33 itens)

1. 🔵 `alembic/0020_…:217` — Seed ICMS por UF com `valid_from=2025-01-01` e fonte "vigentes 2025" rodando em 2026 sem revisão de vigência por UF.
2. 🔵 `icms/calcula_icms.py:50-61` — Alíquotas interestaduais (7%/12%/4%) hardcoded no algoritmo, fora de SCD (as internas estão em tabela).
3. 🔵 `alembic/0019_…:155` — Grupo `servicos_gerais_pequenos` (16%) com `limite_receita_anual=120000` depende do resolver respeitar o teto; conferir que >R$120k cai para 32%.
4. 🔵 `tests/unit/pessoal/test_calcula_distribuicao.py:41-50` — Golden de R$100k esperando 0 retenção fixa o comportamento errado; falta borda R$50.000,01.
5. 🔵 `pessoal/calcula_irrf.py:46` — `ALGORITMO_VERSAO="irrf.mensal.v2"` e docstring citam Lei 14.848/2024; defasará com o redutor 2026.
6. 🔵 `alembic/0058_…:23` — Comentário descreve a faixa 4 do INSS como "teto"; é intervalo. Valor correto.
7. 🔵 `ingestao/parser.py:332-336` — `_decimal()` silencia `InvalidOperation` → R$0,00 sem alarme.
8. 🔵 `ingestao/parser.py:265` — `quantidade if >0 else 1` inventa quantidade 1 silenciosamente.
9. 🔵 `contabil/classificador_cfop.py:34-50` — Mapa CFOP sem 3.xxx (importação/exterior).
10. 🔵 `contabil/classificacao_ncm.py:66-105` — Capítulos NCM heurísticos sem vigência (NESH/SH/TIPI).
11. 🔵 `notas/schemas.py:19-25` — `natureza_operacao: Literal[1,2]` é enum legado da Focus, não o leiaute ADN nacional 2026.
12. 🔵 `ingestao/service.py:96-97` — Cabeçalho herda CFOP/NCM do 1º item; NF multi-CFOP fica enviesada.
13. 🔵 `imobilizado/calcula_depreciacao.py:9-12` — Pro-rata-die não implementado; bem adquirido dia 1º perde 1 mês (decisão consciente, sem golden).
14. 🔵 `contabil/plano_referencial.py:413` — Sintética "5 DESPESAS" → ECD "4.99" não é ancestral das filhas "4.02/4.03/4.05" (sem impacto no arquivo gerado).
15. 🔵 `conciliacao/algoritmo.py:121-134` — Faixa de valor R$5–R$50 não pontua valor mas segue pontuando data/CNPJ.
16. 🔵 `contabil/lancador_auto.py:251` — Falta golden de NF entrada com CFOP de imobilizado (1.551/2.551) → 1.2.3.01.
17. 🔵 `alembic/0054_…:92-113` — UPDATE em `aliquota_cbs_ibs` só sela `valid_to` (tolerável).
18. 🔵 `tabelas_admin/salario_minimo.py:32-41` — Dict de SM histórico hardcoded em .py de produção (reference-only).
19. 🔵 `tabelas_admin/recheck_llm.py:165-189` — Re-check do LLM não bloqueia a criação da sugestão (só sinaliza).
20. 🔵 `alembic/0025/0034` — `conta_contabil` sem trigger SCD nem REVOKE (depende do service).
21. 🔵 `e_cac/classificador.py:141-148` — `_extrair_prazo` usa `date.today()` dentro de função pura.
22. 🔵 `e_cac/classificador.py:128-149` — Prazo extraído é data corrida, sem postergar p/ dia útil nem antecedência.
23. 🔵 `certidoes/service.py:52-56` — CND com 180 dias fixo ignora o campo `validade` do SERPRO.
24. 🔵 `certidoes/service.py:54` — CRF (FGTS) 30 dias sem fonte normativa.
25. 🔵 `reinf/calcula_retencao.py` — R-2010 (INSS 11% cessão de mão de obra) tem enum mas não tem cálculo.
26. 🔵 `reinf/calcula_retencao.py:13-14` — Comentário do limite CSRF com justificativa histórica incoerente (valor correto).
27. 🔵 `certidoes/service.py:323-330` — Fallback `EMITIDA` numa certidão positiva mal-parseada mascara débito.
28. 🔵 `det/service.py` + `monitor_cadastral/service.py` — Sem golden test; DET não calcula prazo da intimação.
29. 🔵 `reforma/calcula_cbs_ibs.py:36` — `algoritmo_versao` duplicado em 3 lugares.
30. 🔵 `alembic/0034:169-171` — Vigência 2027 com `aliquota_cbs=0.0880` preliminar; vigiar fechamento da cadeia.
31. 🔵 `reforma/periodo_transicao.py:8-9` — Docstring omite a condicionante do §3º art.348 (obrigações acessórias).
32. 🔵 `reforma/calcula_cbs_ibs.py:48-61` — Sem flag booleana `informacional` (natureza inferida pelo enum).
33. 🔵 `reforma` (módulo) — PF contribuinte de IBS/CBS (jul/2026) não tratado (não quebra).

---

## VEREDICTO FINAL

**Não vai para produção.** O sistema é bem-arquitetado — SCD honesto, Decimal disciplinado, golden farto, INSS 2026 certo — mas tem **dois erros fiscais ativos desde 01/01/2026 que viram dinheiro errado no bolso do cliente HOJE**: o IRRF roda a tabela de 2024 (cobra a mais de quem a Lei 15.270/2025 isentou) e a distribuição de lucros não retém os 10% obrigatórios sobre o que passa de R$ 50k/mês. Os dois foram confirmados na lei vigente, não são opinião.

Logo atrás vêm cinco críticos que não aparecem no caminho feliz mas explodem na borda: o **Fator R sem encargos** (com a folha vazia no PGDAS) muda o anexo e o valor do DAS; a **DRE conta o IRPJ/CSLL duas vezes**; o **lançador automático não fecha a partida dobrada**; e a **reconciliação NF prometida na docstring simplesmente não existe** — uma mentira no código é pior que uma ausência, porque gera falsa confiança.

O que **não** está errado merece registro: o INSS 2026 está perfeito, as tabelas têm vigência de verdade, a semântica de certidão não está invertida, a Reforma não recolhe nem soma ao total da nota, e a idempotência da emissão está coberta. O sistema sabe fazer o certo — ele só não fez em sete lugares que importam.

**O centavo que importa este mês:** o IRRF. Cada folha fechada de junho/2026 que passar por `calcula_irrf.py` retém imposto que a lei já dispensou. Corrija o #1 antes de qualquer outra coisa.

---

*Auditoria conduzida por 7 auditores especializados (A1–A7) sobre 30 motores `calcula_*.py` e 33 módulos, com reconciliação cruzada do Auditor-Chefe e reconfirmação na web (jun/2026) dos fatos legais que sustentam os achados 🔴. Fontes legais: Lei 15.270/2025 (IRRF + dividendos), Lei 14.438/2022 (FGTS dia 20), Portaria Interministerial MPS/MF 13/2026 (INSS), LC 123/2006 + Res. CGSN 140/2018 (Simples), IN RFB 1.700/2017 (Lucro Presumido), LC 214/2025 (Reforma), IN SRF 162/1998 (depreciação).*
