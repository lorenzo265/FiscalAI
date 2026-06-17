# Validação de Cobertura — MEI e Simples Nacional
## 2026-06-10 | Escopo: VALIDATE — "o app cobre as necessidades contábeis e fiscais de MEIs e PMEs do Simples Nacional?"

Metodologia: pesquisa web (obrigações vigentes em 2026, fontes ao final) cruzada com auditoria do código (`analista-fiscal-api`, 28 módulos, ~14,5k linhas de lógica fiscal, 2520 testes).

---

## Veredito executivo

1. **Simples Nacional (ME/EPP): cobertura forte.** O núcleo de cálculo (DAS, anexos I–V, Fator R, sublimites, partilha), PGDAS-D, DEFIS, folha/pró-labore e contabilidade está implementado e golden-tested. É o melhor do app.
2. **MEI: cobertura parcial e fora do ICP declarado.** O ICP do projeto é R$200k–R$50M/ano; o teto MEI é R$81k. Existe DASN-SIMEI e validação de enquadramento, mas falta o essencial do MEI 2026: emissor NFS-e Nacional e fluxo de desenquadramento MEI→ME.
3. **Gap crítico nº 1: NFS-e padrão nacional (ADN).** Obrigatória para MEI prestador de serviços desde set/2023 e estendida aos optantes do Simples em 2026 (RFB, abr/2026). O app só integra Focus NFE — sem emissor nacional/ADN, o app não cobre a obrigação de documento fiscal mais básica do público-alvo.
4. **Gap crítico nº 2: cadeia eSocial → EFD-Reinf → DCTFWeb.** Payloads e cálculos prontos, mas transmissão real (XML + ICP-Brasil) e orquestração da ordem de dependência ficaram para sprint futura. Sem isso, a folha é "calculadora", não compliance.
5. **Bomba-relógio regulatória:** tabelas INSS/IRRF seedadas são 2025 (pendência #7 já mapeada); multa do PGDAS-D virou automática em 2026 (LC 214/2025); destaque CBS/IBS vira obrigação dos optantes em 2027 — precisa entrar no roadmap agora.

---

## O que o app JÁ FAZ BEM ✅

| Capacidade | Módulo | Obrigação real coberta |
|---|---|---|
| DAS Simples Nacional — anexos I–V, Fator R, sublimite R$3,6M, partilha de tributos, RBT12 | `fiscal/calcula_das.py` | Apuração mensal (venc. dia 20) |
| PGDAS-D | `pgdas` | Declaração mensal obrigatória |
| DEFIS | `declaracao_anual` | Anual, até 31/03 |
| DASN-SIMEI | `declaracao_anual` | Anual MEI, até 31/05 |
| Folha + pró-labore: INSS, IRRF, FGTS (payload eSocial pronto) | `pessoal` | eSocial mensal (quem tem funcionário) |
| Contabilidade: plano referencial, lançamentos, balancete, DRE | `contabil`, `relatorios` | Escrituração / distribuição de lucros |
| Conciliação bancária via open finance (Pluggy) | `open_finance`, `conciliacao` | Dor real nº 1 do dono de PME: caixa vs fisco |
| Agenda de obrigações + multa/juros + parcelamentos | `agenda`, `multa_juros`, `parcelamentos` | Calendário fiscal, atrasos |
| CND federal via SERPRO, monitor cadastral | `certidoes`, `monitor_cadastral` | Certidões e situação cadastral |
| Captura NF-e/NFS-e via Focus NFE + assistente LLM com citação obrigatória + WhatsApp | `notas`, `ingestao`, `assistente`, `whatsapp` | Ingestão de documentos e dúvidas fiscais |
| Distribuição de lucros com limite isento | `lucro_presumido`/`contabil` | Planejamento do sócio |

Engenharia: Decimal-safe em 100% do dinheiro, RLS multi-tenant íntegro, SCD Type 2 nas alíquotas, golden tests bloqueando regressão. Isso é diferencial real frente a concorrentes (Conta Azul/Omie tratam fiscal como módulo acessório).

---

## O que AINDA FALTA ❌ (gaps vs obrigações 2026)

Ordenado por criticidade:

1. **Emissor NFS-e Nacional / ADN** — obrigatório para MEI desde 09/2023; municípios >50k hab. migram exclusivamente ao padrão nacional no 2º semestre/2026; RFB confirmou obrigatoriedade para optantes do Simples. Hoje só existe Focus NFE. *Sem isso o app não emite a nota do seu próprio público.*
2. **Transmissão real do eSocial** (XML + assinatura ICP-Brasil) — payload JSON pronto, envio pendente (pendência consciente #9 do `log_agente.md`).
3. **DCTFWeb + orquestração da cadeia** eSocial (fechamento) → EFD-Reinf → DCTFWeb. Os cálculos existem (`reinf` parcial), mas a sequência obrigatória não é orquestrada. Obrigatória para qualquer SN com funcionário — e para MEI desenquadrado a partir do mês do desenquadramento.
4. **Tabelas INSS/IRRF/FGTS 2026** — seed atual é Portaria 6/2025. DAS-MEI 2026 = R$76,90 (comércio) reajustado pelo salário mínimo de fev/2026. Pendência #7: executar assim que houver valores oficiais no fluxo `/atualizar-aliquota`.
5. **Fluxo de desenquadramento MEI→ME** — regra dos 20% (até R$97.200 → efeito em jan seguinte; acima → retroage a janeiro com tributos recalculados). Não existe simulação nem alerta. Se MEI for ICP, isso é o evento de maior valor do ciclo de vida (é quando ele vira cliente "de verdade" do app).
6. **Desenquadramento do sublimite R$3,6M** — o cálculo respeita o sublimite, mas falta o *workflow* pós-estouro: ICMS/ISS por fora do DAS + obrigações estaduais/municipais (GIA, EFD-ICMS/IPI, DMS). Módulo `icms` cobre só parte.
7. **Reforma Tributária CBS/IBS** — hoje só estimativa educacional. Optantes do SN estão dispensados do destaque em 2026, **mas obrigados a partir de 2027** (campos NT 2025.002: vIBS, vCBS, pIBS, pCBS, cClassTrib, CST). Precisa de sprint dedicada em 2026 H2.
8. **CRF (FGTS) e CNDT** — scraping ainda placeholder (`processando`).
9. **Storage S3/GCS** para recibos SERPRO, DANFSE, holerites — hoje só `storage_key` calculado.
10. **Celery em produção** — beat schedule pronto, pacote opt-in; sem ele não há sync automático (Sintegra/RFB, webhook Pluggy cross-tenant).

---

## O que MELHORAR 🔧 (existe, mas pode render mais)

1. **Multa automática do PGDAS-D (LC 214/2025)** — desde 01/2026 a multa por atraso é aplicada no dia seguinte ao vencimento, sem notificação. A `agenda` deve escalar urgência: alerta D-5, D-1 e dia 20 com tom diferente — o custo do atraso mudou de natureza.
2. **Fator R como produto, não só cálculo** — a pesquisa mostra que ignorar a manutenção dos 28% é o erro nº 1 das PMEs de serviço (Anexo III 6% → Anexo V 15,5%). O cálculo existe; falta o *monitor proativo*: projeção do Fator R do mês seguinte + simulação "aumente o pró-labore em R$X e economize R$Y". É feature de retenção.
3. **Monitor de limites com projeção** — réguas R$81k (MEI), R$3,6M (sublimite) e R$4,8M (teto) com projeção de faturamento anualizado e alerta antes do estouro, não depois. Os dados (notas + open finance) já estão dentro do app.
4. **Bloqueio de lançamento em mês encerrado no service** (pendência #6) — hoje confia no CHECK do banco; erro chega feio ao usuário.
5. **Classificação inteligente de NF de entrada** (pendência #5) — tudo caindo em "5.1.99 A Classificar" degrada o DRE que o dono vê. CFOP/NCM → LLM com re-check determinístico já é o padrão da casa.
6. **Limite isento da distribuição automático** (pendência #10) — hoje é input do contador; o lucro presumido/escrituração já está no sistema para calcular sozinho.

---

## Decisão estratégica pendente: MEI é ICP ou não?

O plano declara ICP R$200k–R$50M (exclui MEI), mas o código já tem DASN-SIMEI e validação SIMEI. Recomendação: **tratar MEI como porta de entrada, não como ICP** — cobrir apenas (a) NFS-e Nacional, (b) alerta de limite R$81k/97,2k e (c) o fluxo de desenquadramento MEI→ME. É barato (DAS-MEI é valor fixo, sem cálculo), captura o cliente no momento em que ele *vira* ME — exatamente quando passa a precisar de tudo que o app já faz bem. Cobertura MEI completa (app concorrendo com a gratuidade do portal do governo) não se paga.

## Próximos passos sugeridos (ordem)

1. Sprint NFS-e Nacional/ADN (gap nº 1 — bloqueia a proposta de valor para serviços).
2. Fechar cadeia eSocial→Reinf→DCTFWeb (transmissão real).
3. Executar `/atualizar-aliquota` quando sair a Portaria 2026 (já acionável, item #9 do branch atual).
4. Monitor proativo de Fator R + limites (melhoria de maior ROI por usar dados já existentes).
5. Planejar sprint CBS/IBS para H2/2026 (deadline real: 01/2027).

---

## Fontes

- [Receita Federal — NFS-e padrão nacional obrigatória para optantes do Simples (abr/2026)](https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/abril/nfs-e-de-padrao-nacional-sera-obrigatoria-para-optantes-do-simples-nacional)
- [Receita Federal — Orientações da Reforma Tributária para 2026](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/reforma-consumo/orientacoes-2026)
- [gov.br — DASN-SIMEI (Declaração Anual de Faturamento do MEI)](https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/servicos-para-mei/declaracao-anual-de-faturamento)
- [gov.br/eSocial — Manual WEB MEI e perguntas frequentes](https://www.gov.br/esocial/pt-br/microempreendedor-individual/manual-web-mei)
- [Contmatic — MEI 2026: limite, DAS e mudanças](https://simplifique.contmatic.com.br/blogs/mei-2026-limite-faturamento-o-que-muda)
- [Contmatic — NFS-e Nacional 2026: o que muda](https://simplifique.contmatic.com.br/blogs/nfse-nacional-2026-o-que-muda-e-como-emitir)
- [Tecnospeed — NFS-e Nacional: prazos e impactos](https://blog.tecnospeed.com.br/nfse-nacional-tudo/)
- [ESN — Obrigações acessórias federais 2026: calendário completo](https://escolasuperioresn.com.br/obrigacoes-acessorias-federais-2026-calendario-completo/)
- [ESN — CBS e IBS em 2026: fase de testes](https://escolasuperioresn.com.br/cbs-ibs-2026-ano-teste-pratica/)
- [e-Auditoria — Obrigações acessórias do Simples Nacional](https://www.e-auditoria.com.br/blog/obrigacoes-acessorias-simples-nacional-guia-completo/)
- [eSimples — 10 erros mais comuns no Simples Nacional (Fator R, sublimites)](https://www.esimplesauditoria.com/erros-no-simples-nacional)
- [eSimples — IBS e CBS no Simples Nacional](https://www.esimplesauditoria.com/ibs-e-cbs-simples-nacional)
- [VRF — Desenquadramento do sublimite do Simples Nacional](https://vrfcontabilidade.com.br/quando-ocorre-o-desenquadramento-do-sublimite-do-simples-nacional-como-evitar/)
- [Fenafisco — Quando o destaque de IBS/CBS na NF vira obrigatório](https://fenafisco.org.br/08/04/2026/reforma-tributaria-afinal-quando-o-destaque-de-ibs-e-cbs-na-nota-fiscal-passa-a-ser-realmente-obrigatorio/)
- [Tecnospeed — DCTFWeb: obrigatoriedade e prazos](https://blog.tecnospeed.com.br/dctfweb-o-que-e/)
- [Marchesan — MEI com funcionário: regras 2026](https://marchesan.co/blog/mei-pode-ter-funcionario)
