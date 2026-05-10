"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { perfMark } from "@/lib/perf";

export function useApuracaoAtual() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["fiscal", "apuracao-atual", empresa?.cnpj, empresa?.faturamento12m],
    queryFn: async () => {
      const stop = perfMark("query:apuracao-atual");
      const r = await api.fiscal.apuracaoAtual(empresa);
      stop();
      return r;
    },
    enabled: !!empresa,
    staleTime: 60_000,
  });
}
