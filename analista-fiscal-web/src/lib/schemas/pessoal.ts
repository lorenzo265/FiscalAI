import { z } from "zod";

export const tipoContratoSchema = z.enum(["CLT", "PJ", "ESTAGIO"]);
export type TipoContrato = z.infer<typeof tipoContratoSchema>;

export const TIPO_CONTRATO_LABEL: Record<TipoContrato, string> = {
  CLT: "CLT",
  PJ: "PJ (prestador)",
  ESTAGIO: "Estagiário",
};

export const statusFuncionarioSchema = z.enum([
  "ativo",
  "afastado",
  "demitido",
]);
export type StatusFuncionario = z.infer<typeof statusFuncionarioSchema>;

export const STATUS_FUNCIONARIO_LABEL: Record<StatusFuncionario, string> = {
  ativo: "Ativo",
  afastado: "Afastado",
  demitido: "Demitido",
};

export const generoSchema = z.enum(["M", "F", "X"]);
export type Genero = z.infer<typeof generoSchema>;

export const funcionarioSchema = z.object({
  id: z.string(),
  nome: z.string(),
  cpf: z.string(),
  email: z.string().email().optional(),
  telefone: z.string().optional(),
  dataNascimento: z.string(),
  genero: generoSchema,
  cargo: z.string(),
  setor: z.string().optional(),
  tipoContrato: tipoContratoSchema,
  jornadaSemanal: z.number().int().min(1).max(44),
  salario: z.number().nonnegative(),
  dataAdmissao: z.string(),
  dataDemissao: z.string().optional(),
  status: statusFuncionarioSchema,
  avatarSeed: z.string(),
  pisPasep: z.string().optional(),
});
export type Funcionario = z.infer<typeof funcionarioSchema>;
export const funcionariosSchema = z.array(funcionarioSchema);

export const funcionarioInputSchema = z.object({
  nome: z.string().min(3, "Informe o nome completo"),
  cpf: z.string().min(11, "CPF inválido").max(14),
  email: z
    .string()
    .email("E-mail inválido")
    .optional()
    .or(z.literal("")),
  telefone: z.string().optional().or(z.literal("")),
  dataNascimento: z.string().min(10, "Informe a data"),
  genero: generoSchema,
  cargo: z.string().min(2, "Informe o cargo"),
  setor: z.string().optional().or(z.literal("")),
  tipoContrato: tipoContratoSchema,
  jornadaSemanal: z.coerce.number().int().min(1).max(44),
  salario: z.coerce.number().min(0),
  dataAdmissao: z.string().min(10, "Informe a data de admissão"),
});
export type FuncionarioInput = z.infer<typeof funcionarioInputSchema>;

export const tipoEventoFolhaSchema = z.enum(["provento", "desconto"]);
export type TipoEventoFolha = z.infer<typeof tipoEventoFolhaSchema>;

export const eventoFolhaSchema = z.object({
  codigo: z.string(),
  descricao: z.string(),
  referencia: z.string(),
  tipo: tipoEventoFolhaSchema,
  valor: z.number().nonnegative(),
});
export type EventoFolha = z.infer<typeof eventoFolhaSchema>;

export const statusHoleriteSchema = z.enum(["gerado", "pago"]);
export type StatusHolerite = z.infer<typeof statusHoleriteSchema>;

export const holeriteSchema = z.object({
  id: z.string(),
  funcionarioId: z.string(),
  funcionarioNome: z.string(),
  cargo: z.string(),
  ano: z.number().int(),
  mes: z.number().int().min(1).max(12),
  competencia: z.string(),
  diasTrabalhados: z.number().int(),
  salarioBase: z.number(),
  totalProventos: z.number(),
  totalDescontos: z.number(),
  totalLiquido: z.number(),
  baseInss: z.number(),
  baseFgts: z.number(),
  baseIrrf: z.number(),
  fgts: z.number(),
  inssEmpresa: z.number(),
  eventos: z.array(eventoFolhaSchema),
  status: statusHoleriteSchema,
  geradoEm: z.string(),
  pagoEm: z.string().optional(),
});
export type Holerite = z.infer<typeof holeriteSchema>;
export const holeritesSchema = z.array(holeriteSchema);

export const tipoEventoEsocialSchema = z.enum([
  "S-2200",
  "S-2299",
  "S-1200",
  "S-1210",
  "S-1299",
  "S-2230",
]);
export type TipoEventoEsocial = z.infer<typeof tipoEventoEsocialSchema>;

export const TIPO_EVENTO_ESOCIAL_LABEL: Record<TipoEventoEsocial, string> = {
  "S-2200": "Admissão de trabalhador",
  "S-2299": "Desligamento",
  "S-1200": "Remuneração da folha",
  "S-1210": "Pagamentos diversos",
  "S-1299": "Fechamento da folha",
  "S-2230": "Afastamento temporário",
};

export const statusEventoEsocialSchema = z.enum([
  "transmitido",
  "pendente",
  "erro",
  "rascunho",
]);
export type StatusEventoEsocial = z.infer<typeof statusEventoEsocialSchema>;

export const eventoEsocialSchema = z.object({
  id: z.string(),
  tipo: tipoEventoEsocialSchema,
  funcionarioId: z.string().optional(),
  funcionarioNome: z.string().optional(),
  competencia: z.string(),
  status: statusEventoEsocialSchema,
  recibo: z.string().optional(),
  motivoErro: z.string().optional(),
  transmitidoEm: z.string().optional(),
  criadoEm: z.string(),
});
export type EventoEsocial = z.infer<typeof eventoEsocialSchema>;
export const eventosEsocialSchema = z.array(eventoEsocialSchema);

export const folhaResumoSchema = z.object({
  ano: z.number().int(),
  mes: z.number().int().min(1).max(12),
  totalBruto: z.number(),
  totalLiquido: z.number(),
  totalDescontos: z.number(),
  totalInssEmpresa: z.number(),
  totalFgts: z.number(),
  totalFuncionarios: z.number(),
  status: z.enum(["aberta", "fechada", "transmitida"]),
});
export type FolhaResumo = z.infer<typeof folhaResumoSchema>;
