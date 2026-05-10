"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function useAgenda() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["agenda", "mes", empresa?.cnpj, new Date().getMonth()],
    queryFn: () => api.agenda.listar(empresa),
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}

export function useAgendaMes(ano: number, mes: number) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["agenda", "mes", empresa?.cnpj, ano, mes],
    queryFn: () => api.agenda.listarMes(empresa, ano, mes),
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}

export function useAgendaAno(ano: number) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["agenda", "ano", empresa?.cnpj, ano],
    queryFn: () => api.agenda.listarAno(empresa, ano),
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}
