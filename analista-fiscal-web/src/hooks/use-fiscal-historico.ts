"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function useFiscalHistorico(meses = 6) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: [
      "fiscal",
      "historico",
      meses,
      empresa?.cnpj,
      empresa?.faturamento12m,
    ],
    queryFn: () => api.fiscal.historico(empresa, meses),
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}
