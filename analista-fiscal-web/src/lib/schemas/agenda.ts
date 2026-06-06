import { z } from "zod";

/**
 * `EventoAgenda` — contrato que as TELAS consomem (calendário, lista anual,
 * próximos vencimentos). NÃO é o shape cru do backend: o adapter
 * `src/lib/api/agenda.ts` traduz `AgendaItemOut` → `EventoAgenda`.
 *
 * Campos `valor`/`rota` são opcionais e hoje NÃO têm origem no backend
 * (o calendário fiscal não calcula valores) — ficam `undefined`.
 */
export const eventoAgendaSchema = z.object({
  id: z.string(),
  data: z.string(),
  titulo: z.string(),
  descricao: z.string(),
  tipo: z.enum([
    "imposto",
    "obrigacao_acessoria",
    "folha",
    "esocial",
    "informativo",
  ]),
  status: z.enum(["pago", "pendente", "atrasado", "informativo"]),
  valor: z.number().optional(),
  rota: z.string().optional(),
});
export type EventoAgenda = z.infer<typeof eventoAgendaSchema>;

export const eventosAgendaSchema = z.array(eventoAgendaSchema);

// ── Shape REAL do backend (`AgendaItemOut` / `AgendaListaOut`) ────────────────
// Validado após `toCamel` (backend é snake_case). Usado pelo adapter para
// parsear a resposta antes de mapear para `EventoAgenda`.

/** `status` backend: ck_agenda_status = pendente | concluido | vencido. */
export const agendaItemOutSchema = z.object({
  id: z.string(),
  titulo: z.string(),
  descricao: z.string().nullable(),
  dataVencimento: z.string(), // ISO date YYYY-MM-DD
  regime: z.string(),
  tipoObrigacao: z.string(),
  status: z.string(),
});
export type AgendaItemOut = z.infer<typeof agendaItemOutSchema>;

export const agendaListaOutSchema = z.object({
  empresaId: z.string(),
  ano: z.number(),
  total: z.number(),
  itens: z.array(agendaItemOutSchema),
});
export type AgendaListaOut = z.infer<typeof agendaListaOutSchema>;
