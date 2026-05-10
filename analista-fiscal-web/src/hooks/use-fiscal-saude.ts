"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { perfMark } from "@/lib/perf";

export function useFiscalSaude() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["fiscal", "saude", empresa?.cnpj, empresa?.faturamento12m],
    queryFn: async () => {
      const stop = perfMark("query:fiscal-saude");
      const r = await api.fiscal.saude(empresa);
      stop();
      return r;
    },
    enabled: !!empresa,
    staleTime: 60_000,
  });
}
