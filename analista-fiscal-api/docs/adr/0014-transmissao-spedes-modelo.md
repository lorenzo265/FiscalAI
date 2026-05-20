# ADR 0014 — Modelo de transmissão de SPED e apurações ao Fisco

- **Status:** Aceito
- **Data:** 2026-05-18
- **Decisor:** Tech Lead Backend + Consultor contábil (CRC)
- **Substitui/relaciona:** —
- **Sprint:** Resolução de contradição §7.7 vs §8.12 do `PlanoBackend.md` (Fase 1.2 do plano de remediação)

## Contexto

O `PlanoBackend.md` v2.0 continha **contradição direta** entre §7.7 ("Não transmitimos automaticamente — requer certificado A1 + ação consciente do cliente") e §8.12 ("Para PGDAS-D, DCTFWeb, DCTF: cliente assina termo de delegação no onboarding; transmissão automática via SERPRO com certificado dele (armazenado criptografado)"). Além de inconsistente, o modelo descrito em §8.12 tem 2 problemas técnicos sérios:

1. **Armazenar certificado A1 (chave privada) de cliente** para assinar atos digitais perante a RFB é território regulado: exige cuidados que vão além de `pgcrypto + KMS` (auditoria CFC, política de chaves, separação de duties). Risco regulatório alto.
2. **SERPRO Integra Contador opera com certificado do escritório contábil + procuração eletrônica e-CAC** outorgada pelo cliente. **NÃO** opera com cert do cliente. O texto original confundia os dois fluxos.

Adicionalmente, SPED (ECD, ECF, EFD-Contribuições, EFD ICMS-IPI) tem fluxo distinto — transmitido via PVA/ReceitaNet com certificado do contribuinte — e não passa pelo SERPRO.

## Decisão

Adotar **dois fluxos distintos**, ambos com a regra invariante "**não armazenamos cert A1 do cliente em nenhum caso**":

### Fluxo A — SPED (ECD, ECF, EFD-Contribuições, EFD ICMS-IPI)

1. Sistema gera arquivo `.txt` no layout oficial (parser custom, eventualmente forkando `python-sped`).
2. Sistema valida localmente (sintática + amarrações cross-bloco).
3. Sistema mostra erros e advertências.
4. **Cliente ou contador baixa o arquivo** e transmite via PVA/ReceitaNet **com o certificado A1 dele próprio**.
5. Audit trail registra: usuário, IP, hash do arquivo, timestamp do download.
6. Sistema **nunca** transmite SPED automaticamente.

### Fluxo B — PGDAS-D, DCTFWeb, DCTF mensal, EFD-Reinf (via SERPRO Integra Contador)

1. Cliente outorga **procuração eletrônica e-CAC** para o CNPJ do escritório contábil (nosso tenant) — passo único, feito no e-CAC com cert do próprio cliente, fora do nosso sistema.
2. Cliente assina, dentro do nosso sistema, um termo digital autorizando o escritório a utilizar a procuração para transmitir suas obrigações; data e IP ficam no `audit_log`.
3. Quando o sistema transmite, usa **cert A1 do escritório** (armazenado criptografado via `pgcrypto + KMS`) + token SERPRO + número da procuração eletrônica do cliente.
4. SERPRO valida procuração + certificado e devolve recibo, que persistimos.
5. Audit trail amarra: usuário que disparou, IP, cert utilizado (escritório), procuração consumida, recibo SERPRO, timestamp.

### Invariantes

- **`certificado_a1` no banco só pode pertencer a CNPJ de tenant (escritório).** CHECK constraint adicionada na tabela.
- Tentativa de armazenar cert vinculado a CNPJ de empresa-cliente é rejeitada na inserção.
- O termo de delegação eletrônico é versionado em `consentimento_versionado` (LGPD §8.7).

## Alternativas consideradas

- **A1 — Transmissão automática com cert do cliente armazenado**: rejeitada. Risco regulatório alto (responsabilidade técnica, política de chaves) e diverge do modelo oficial SERPRO Integra Contador.
- **A2 — Cliente transmite tudo manualmente, sempre**: rejeitada para PGDAS-D/DCTFWeb/DCTF — esses são fluxos onde o cliente já espera que o contador transmita. Forçar transmissão manual para esses inviabiliza o produto.
- **A3 — Manter SPED manual e PGDAS via procuração e-CAC** (decisão adotada): combina segurança jurídica + UX adequada por canal.

## Consequências

### Positivas
- Conformidade com modelo oficial SERPRO Integra Contador.
- Risco regulatório reduzido (não somos custodiantes de chaves do cliente).
- Audit trail claro de quem usou qual cert para transmitir o quê.
- Permite que escritório contábil multi-cliente (tenant com N empresas) opere normalmente.

### Negativas
- Onboarding fica com 2 passos extras: (a) cliente outorga procuração no e-CAC, fora do nosso sistema; (b) cliente assina termo dentro do sistema. Atrito real no setup.
- Sistema **não cobre** clientes que não querem outorgar procuração — para esses, PGDAS-D entra no mesmo modelo do SPED (manual).
- Cliente que troca de contador precisa revogar procuração no e-CAC antes que o escritório antigo perca acesso — comunicação cuidadosa no churn.

## Plano de aplicação

1. Refatorar `app/modules/pgdas/service.py` para validar presença de procuração antes de chamar SERPRO.
2. Criar tabela `procuracao_ecac (empresa_id, escritorio_cnpj, numero_procuracao, valid_from, valid_to, status)` na próxima migration de hardening (Fase 2).
3. Endpoint novo `POST /v1/empresas/{eid}/procuracao-ecac` para cliente registrar dados da procuração após outorga no e-CAC.
4. UI no onboarding com passo "outorgar procuração" + link explicativo.
5. Atualizar termos de uso (revisar com advogado LGPD).
6. Documentar em runbook operacional o fluxo de churn (revogação).

## Referências

- §7.7, §8.12 do `PlanoBackend.md` (após Fase 1.2)
- Decreto 70.235/1972 (Processo Administrativo Fiscal)
- Resolução CFC 1.554/2018 (procuração eletrônica e responsabilidade técnica)
- Documentação SERPRO Integra Contador: https://apicenter.estaleiro.serpro.gov.br/
