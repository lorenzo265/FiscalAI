/**
 * Shim de compatibilidade (Fase A — Fundação).
 *
 * O monolito `api-client.ts` foi dividido em `src/lib/api/<dominio>.ts` +
 * barrel `src/lib/api/index.ts`. Este arquivo apenas re-exporta `api` e
 * `ApiError` para não quebrar os imports existentes
 * (`import { api, ApiError } from "@/lib/api-client"`).
 *
 * Comportamento de dados é IDÊNTICO ao anterior — nada migrou para o backend
 * real nesta fase. Cada agente de domínio reescreve o seu arquivo em
 * `src/lib/api/`.
 */
export { api, ApiError } from "@/lib/api";
