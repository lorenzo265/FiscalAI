"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  adicionarLancamento,
  garantirSeedContabil,
  listarLancamentos,
  removerLancamento,
} from "@/lib/contabil/db-service";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import type { LancamentoContabil } from "@/lib/schemas/contabil";

export function useLancamentos() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["contabil", "lancamentos", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedContabil(empresa);
      return listarLancamentos();
    },
    enabled: !!empresa,
  });
}

export function useAdicionarLancamento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (lancamento: LancamentoContabil) => {
      await adicionarLancamento(lancamento);
      return lancamento;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["contabil"] });
    },
  });
}

export function useRemoverLancamento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await removerLancamento(id);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["contabil"] });
    },
  });
}
