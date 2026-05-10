import type { Empresa } from "@/lib/schemas/empresa";

const seedsEmExecucao = new Map<string, Promise<void>>();

/**
 * Dispara todos os seeds dos módulos em paralelo, uma única vez por empresa
 * por sessão. Hooks individuais ainda podem chamar seu garantirSeed; este
 * apenas antecipa o trabalho durante o boot, em paralelo.
 *
 * Importa lazy pra não inflar o bundle do EmpresaProvider.
 */
export function garantirTodosSeeds(empresa: Empresa): Promise<void> {
  const chave = empresa.cnpj;
  const existente = seedsEmExecucao.get(chave);
  if (existente) return existente;

  const promise = (async () => {
    const [
      { garantirSeedNotas },
      { garantirSeedContabil },
      { garantirSeedControles },
      { garantirSeedPessoal },
      { garantirSeedCompliance },
      { garantirSeedAssistente },
    ] = await Promise.all([
      import("@/lib/notas/db-service"),
      import("@/lib/contabil/db-service"),
      import("@/lib/controles/db-service"),
      import("@/lib/pessoal/db-service"),
      import("@/lib/compliance/db-service"),
      import("@/lib/assistente/db-service"),
    ]);

    await Promise.all([
      garantirSeedNotas(empresa),
      garantirSeedContabil(empresa),
      garantirSeedControles(empresa),
      garantirSeedPessoal(empresa),
      garantirSeedCompliance(empresa),
      garantirSeedAssistente(empresa),
    ]);
  })();

  seedsEmExecucao.set(chave, promise);
  return promise;
}
