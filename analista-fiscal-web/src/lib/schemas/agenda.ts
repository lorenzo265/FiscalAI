import { z } from "zod";

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
