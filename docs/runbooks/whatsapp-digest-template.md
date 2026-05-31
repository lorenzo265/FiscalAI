---
tags: [runbook, whatsapp, meta, digest, sprint-15-5]
fonte: "Sprint 15.5 — envio real do weekly digest"
atualizado: 2026-05-24
---

# Runbook — Cadastro do template WhatsApp `weekly_digest_pt_br`

> Pré-requisito para ativar o envio real do digest semanal do AI Advisor
> (Sprint 15 PR3 + Sprint 15.5 PR1–PR4). Sem template aprovado, a flag
> `WHATSAPP_DIGEST_TEMPLATE_ATIVO` fica em `False` e os digests são
> apenas persistidos com `status='preparado'`.

## Visão geral

O envio do digest usa um **template Meta UTILITY** (regulatory/transactional)
disparado por worker Celery (segunda 06:30 BR). Diferente de mensagens de
texto livre (que só funcionam dentro da janela de 24h após o cliente escrever
ao número), templates **podem ser enviados a qualquer momento** desde que:

1. O template esteja **aprovado** pela Meta.
2. O destinatário tenha **opt-in** registrado para receber mensagens da empresa.
3. A categoria UTILITY seja respeitada (mensagem relacionada a serviço já
   contratado, sem promoção comercial).

## 1. Cadastro do template (Meta Business Manager)

1. Acessar [business.facebook.com](https://business.facebook.com/) com a conta
   business associada ao número WhatsApp Business da plataforma.
2. **WhatsApp Manager** → **Templates de mensagem** → **Criar modelo**.
3. Preencher:

   | Campo | Valor |
   |---|---|
   | **Categoria** | `UTILITY` |
   | **Nome** | `weekly_digest_pt_br` |
   | **Idiomas** | `Português (BR)` (code: `pt_BR`) |

4. **Cabeçalho** (opcional): `Texto` → `Resumo semanal do seu negócio`
5. **Corpo** (obrigatório):

   ```text
   Olá {{1}}!

   {{2}}

   Acesse o app para detalhes: https://app.analista-fiscal.com.br
   ```

6. **Rodapé** (opcional): `Analista Fiscal — seu contador IA.`
7. **Botões** (opcional, recomendado): `Botão de site` → `Abrir app` → URL acima.
8. **Variáveis de amostra** (a Meta exige exemplos para revisão):
   - `{{1}}`: `ACME`
   - `{{2}}`: `Apurações fechadas: DAS 2026-04-01 R$ 1.234,56. Próximos vencimentos: DAS abril/2026 vence em 2026-05-22.`

9. **Enviar para revisão**. Aprovação leva tipicamente **1–24 horas**.

## 2. Configurar a env var

Após aprovação, no ambiente (Kubernetes secret / `.env` local):

```bash
WHATSAPP_DIGEST_TEMPLATE_NAME=weekly_digest_pt_br
WHATSAPP_DIGEST_LANG_CODE=pt_BR
WHATSAPP_DIGEST_TEMPLATE_ATIVO=true
```

> O default seguro é `WHATSAPP_DIGEST_TEMPLATE_ATIVO=false`. Em ambientes
> sem template aprovado, manter desativado evita ruído de logs e custos.

## 3. Validar end-to-end

```bash
# Disparar manualmente para uma empresa de teste
curl -X POST https://api.analista-fiscal.com.br/v1/empresas/{EMPRESA_ID}/advisor/digest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"forcar": true}'

# Envio explícito (gera primeiro, envia depois)
curl -X POST https://api.analista-fiscal.com.br/v1/empresas/{EMPRESA_ID}/advisor/digests/{DIGEST_ID}/enviar \
  -H "Authorization: Bearer $TOKEN"
```

Resposta esperada (caminho feliz):

```json
{
  "status": "enviado",
  "enviado_via_whatsapp_em": "2026-05-26T09:30:42-03:00",
  "enviado_template_name": "weekly_digest_pt_br",
  "tentativas_envio": 1,
  "ultimo_erro_envio": null
}
```

## 4. Troubleshooting

| Sintoma | Causa provável | Resolução |
|---|---|---|
| `Meta WhatsApp 400: template not approved` | Template ainda em revisão ou rejeitado | Aguardar; em caso de rejeição, ler feedback Meta e re-submeter |
| `Meta WhatsApp 400: 24h window` | Categoria UTILITY caiu fora da janela 24h | Cliente precisa interagir ao menos 1x antes do envio, OU promover para `MARKETING` (com custo) |
| `Meta WhatsApp 400: variable count mismatch` | Template aprovado tem N variáveis e código envia M | Sincronizar template + `body_parameters` |
| `WHATSAPP_DIGEST_TEMPLATE_ATIVO=False` | Flag não ativada após aprovação | Setar env var + restart |
| `status='falhou'` após 5 ciclos | Meta indisponível por 5+ semanas OU template removido | Investigar template no Meta Manager + resetar `tentativas_envio` manualmente |
| `tentativas_envio=N, status='preparado'` | Falha transitória — beat tenta novamente na próxima segunda | Esperar próximo ciclo; após 5 ciclos vira `falhou` |

## 5. Custos esperados

- **UTILITY** dentro da janela 24h: gratuito.
- **UTILITY** fora da janela 24h: cobrado como conversa de **serviço** (~US$ 0,008/mensagem em jul/2025).
- **MARKETING**: cobrado como conversa de **marketing** (~US$ 0,025/mensagem).
- 100 empresas × 4 semanas/mês = ~400 mensagens/mês → **<R$ 25/mês** (mesmo no pior caso MARKETING).

## 6. Pendências futuras

- Revisar custo real após primeiro mês em produção (Grafana `whatsapp.template.enviado` count + Meta billing).
- Considerar opt-in explícito do cliente (LGPD) antes de enviar primeiro digest.
- Investigar `MARKETING` se UTILITY for rejeitada por categoria errada.

Relacionado: `app/modules/advisor/service.py::enviar_digest_via_whatsapp`,
`app/workers/tasks/advisor_enviar_digests.py`,
`app/shared/integrations/meta_whatsapp/sender.py::enviar_template`.
