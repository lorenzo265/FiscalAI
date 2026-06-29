"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

/** Simulação CBS/IBS real (`GET /empresas/{id}/reforma/simulacao`). */
export function useSimulacaoReforma(anoAlvo = 2033) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["reforma", "simulacao", empresa?.cnpj, anoAlvo],
    queryFn: () => api.reforma.simulacao(anoAlvo),
    enabled: !!empresa,
  });
}
