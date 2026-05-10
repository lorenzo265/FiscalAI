"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function useFiscalGuias() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: [
      "fiscal",
      "guias",
      empresa?.cnpj,
      empresa?.faturamento12m,
      empresa?.anexoSimples,
    ],
    queryFn: () => api.fiscal.guias(empresa),
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}
