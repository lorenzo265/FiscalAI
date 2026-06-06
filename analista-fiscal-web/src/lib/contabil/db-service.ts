/**
 * Service de contábil — Onda 2: passou de Dexie/mock para a API real.
 *
 * Mantém a SUPERFÍCIE pública que os consumidores já usam (o hook
 * `use-contabil` e o adapter de `relatorios`), mas a fonte de verdade agora é o
 * backend FastAPI (`@/lib/api/contabil`). Não há mais seed local de
 * lançamentos — os dados vêm do módulo contábil do servidor.
 *
 * `garantirSeedContabil` vira no-op (o backend é a fonte). É mantida apenas
 * para preservar a assinatura chamada por `garantir-todos.ts` e pelo hook.
 */
import type { Empresa } from "@/lib/schemas/empresa";

export {
  listarLancamentos,
  adicionarLancamento,
  removerLancamento,
} from "@/lib/api/contabil";

/**
 * No-op de compatibilidade. A contabilidade agora é lida do backend; não há
 * seed local a popular. Mantida para não quebrar os chamadores existentes
 * (`garantirTodosSeeds`, `useLancamentos`).
 */
export async function garantirSeedContabil(_empresa: Empresa): Promise<void> {
  return;
}
