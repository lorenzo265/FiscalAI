import { z } from "zod";

export const guiaDASSchema = z.object({
  id: z.string(),
  periodo: z.object({ ano: z.number(), mes: z.number() }),
  rotulo: z.string(),
  numeroDocumento: z.string(),
  codigoBarras: z.string(),
  faturamentoMes: z.number(),
  aliquotaEfetiva: z.number(),
  valor: z.number(),
  vencimento: z.string(),
  pagaEm: z.string().nullable(),
  status: z.enum(["em_aberto", "pago", "atrasado"]),
  pixCopiaCola: z.string(),
});
export type GuiaDAS = z.infer<typeof guiaDASSchema>;

export const guiasDASSchema = z.array(guiaDASSchema);
