/**
 * Barrel da API (Fase A — Fundação). Monta `api` na MESMA forma do
 * monolito `api-client.ts` original, agora composto a partir de um arquivo por
 * domínio (`src/lib/api/<dominio>.ts`). Cada agente de domínio reescreve só o
 * seu arquivo para falar com o backend real, sem colisão de merge.
 *
 * `ApiError` é reexportada de `@/lib/http` (a real). Imports existentes
 * (`import { api, ApiError } from "@/lib/api-client"`) continuam válidos via o
 * shim em `src/lib/api-client.ts`.
 */
export { ApiError } from "@/lib/http";

import { auth } from "@/lib/api/auth";
import { empresa } from "@/lib/api/empresa";
import { fiscal } from "@/lib/api/fiscal";
import { agenda } from "@/lib/api/agenda";
import { notas } from "@/lib/api/notas";
import { controles } from "@/lib/api/controles";
import { pessoal } from "@/lib/api/pessoal";
import { contabil } from "@/lib/api/contabil";
import { assistente } from "@/lib/api/assistente";
import { compliance } from "@/lib/api/compliance";
import { relatorios } from "@/lib/api/relatorios";

export const api = {
  auth,
  empresa,
  fiscal,
  agenda,
  notas,
  controles,
  pessoal,
  contabil,
  assistente,
  compliance,
  relatorios,
};
