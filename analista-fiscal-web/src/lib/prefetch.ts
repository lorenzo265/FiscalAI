import type { QueryClient } from "@tanstack/react-query";
import type { Empresa } from "@/lib/schemas/empresa";
import type { ModuloId } from "@/components/layout/nav-config";

/**
 * Prefetch da query primária de cada módulo.
 *
 * Acionado por hover/pointer-enter nos itens da Sidebar.
 * Lazy-importa o api-client e os db-services pra não inflar o boot.
 *
 * Idempotente: TanStack Query deduplica por queryKey + respeita staleTime.
 * Se a query já foi feita há <60s, não dispara nada.
 */
export async function prefetchModulo(
  qc: QueryClient,
  modulo: ModuloId,
  empresa: Empresa | null
): Promise<void> {
  if (!empresa) return;

  switch (modulo) {
    case "home": {
      const { api } = await import("@/lib/api-client");
      await qc.prefetchQuery({
        queryKey: ["fiscal", "saude", empresa.cnpj, empresa.faturamento12m],
        queryFn: () => api.fiscal.saude(empresa),
        staleTime: 60_000,
      });
      return;
    }
    case "fiscal": {
      const { api } = await import("@/lib/api-client");
      await qc.prefetchQuery({
        queryKey: [
          "fiscal",
          "apuracao-atual",
          empresa.cnpj,
          empresa.faturamento12m,
        ],
        queryFn: () => api.fiscal.apuracaoAtual(empresa),
        staleTime: 60_000,
      });
      return;
    }
    case "notas": {
      const { listarNotas } = await import("@/lib/notas/db-service");
      await qc.prefetchQuery({
        queryKey: ["notas", "list", empresa.cnpj],
        queryFn: () => listarNotas(),
      });
      return;
    }
    case "controles": {
      const { api } = await import("@/lib/api-client");
      await qc.prefetchQuery({
        queryKey: ["controles", "bancos", empresa.cnpj],
        queryFn: () => api.controles.listarBancos(),
      });
      return;
    }
    case "pessoal": {
      const { api } = await import("@/lib/api-client");
      await qc.prefetchQuery({
        queryKey: ["pessoal", "funcionarios", empresa.cnpj],
        queryFn: () => api.pessoal.listarFuncionarios(),
      });
      return;
    }
    case "compliance": {
      const { api } = await import("@/lib/api-client");
      await qc.prefetchQuery({
        queryKey: ["compliance", "painel", empresa.cnpj],
        queryFn: () => api.compliance.painel(),
      });
      return;
    }
    case "agenda": {
      const { api } = await import("@/lib/api-client");
      const hoje = new Date();
      await qc.prefetchQuery({
        queryKey: ["agenda", "mes", empresa.cnpj, hoje.getMonth()],
        queryFn: () => api.agenda.listar(empresa),
        staleTime: 5 * 60_000,
      });
      return;
    }
    default:
      return;
  }
}
