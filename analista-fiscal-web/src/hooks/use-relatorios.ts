"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { garantirSeedContabil } from "@/lib/contabil/db-service";
import { garantirSeedControles } from "@/lib/controles/db-service";
import { garantirSeedPessoal } from "@/lib/pessoal/db-service";

async function garantirTudo(
  empresa: import("@/lib/schemas/empresa").Empresa | null
) {
  if (!empresa) return;
  await garantirSeedContabil(empresa);
  await garantirSeedControles(empresa);
  await garantirSeedPessoal(empresa);
}

export function useDRE() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["relatorios", "dre", empresa?.cnpj],
    queryFn: async () => {
      await garantirTudo(empresa);
      return api.relatorios.dre();
    },
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}

export function useBalanco() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["relatorios", "balanco", empresa?.cnpj],
    queryFn: async () => {
      await garantirTudo(empresa);
      return api.relatorios.balanco();
    },
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}

export function useDFC() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["relatorios", "dfc", empresa?.cnpj],
    queryFn: async () => {
      await garantirTudo(empresa);
      return api.relatorios.dfc();
    },
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}

export function useIndicadores() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["relatorios", "indicadores", empresa?.cnpj],
    queryFn: async () => {
      await garantirTudo(empresa);
      return api.relatorios.indicadores();
    },
    enabled: !!empresa,
    staleTime: 5 * 60_000,
  });
}
