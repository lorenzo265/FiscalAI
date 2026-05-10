import { z } from "zod";

export const cnpjLookupResponseSchema = z.object({
  cnpj: z.string(),
  razaoSocial: z.string(),
  nomeFantasia: z.string(),
  cnaePrincipal: z.object({
    codigo: z.string(),
    descricao: z.string(),
  }),
  cnaesSecundarios: z.array(
    z.object({ codigo: z.string(), descricao: z.string() })
  ),
  endereco: z.object({
    logradouro: z.string(),
    numero: z.string(),
    complemento: z.string().optional(),
    bairro: z.string(),
    municipio: z.string(),
    uf: z.string().length(2),
    cep: z.string(),
  }),
  porte: z.string(),
  situacao: z.enum(["ATIVA", "BAIXADA", "INAPTA", "SUSPENSA"]),
  dataAbertura: z.string(),
  socios: z.array(
    z.object({
      cpf: z.string(),
      nome: z.string(),
      participacao: z.number(),
      isAdministrador: z.boolean(),
    })
  ),
});

export type CnpjLookupResponse = z.infer<typeof cnpjLookupResponseSchema>;
