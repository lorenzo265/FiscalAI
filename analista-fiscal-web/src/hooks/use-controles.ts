"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { garantirSeedControles } from "@/lib/controles/db-service";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import type { ContaPagarReceber } from "@/lib/schemas/controles";
import { perfMark } from "@/lib/perf";

export function useBancos() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["controles", "bancos", empresa?.cnpj],
    queryFn: async () => {
      const stopSeed = perfMark("seed:controles");
      if (empresa) await garantirSeedControles(empresa);
      stopSeed();
      const stop = perfMark("query:bancos");
      const r = await api.controles.listarBancos();
      stop();
      return r;
    },
    enabled: !!empresa,
  });
}

export function useBanco(id: string) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["controles", "bancos", empresa?.cnpj, id],
    queryFn: async () => {
      if (empresa) await garantirSeedControles(empresa);
      const conta = await api.controles.obterBanco(id);
      if (!conta) throw new Error("Conta não encontrada");
      return conta;
    },
    enabled: !!empresa && !!id,
  });
}

export function useSincronizarBanco() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.controles.sincronizarBanco(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["controles"] });
    },
  });
}

export function useConectarBanco() {
  const { empresa } = useEmpresaAtual();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (bancoId: string) => {
      if (!empresa) throw new Error("empresa indisponível");
      return api.controles.conectarBanco(empresa, bancoId);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["controles"] });
    },
  });
}

export function useTransacoes(contaId: string) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["controles", "transacoes", empresa?.cnpj, contaId],
    queryFn: () => api.controles.listarTransacoes(contaId),
    enabled: !!empresa && !!contaId,
  });
}

export function useConciliarTransacao() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      transacaoId,
      lancamentoId,
    }: {
      transacaoId: string;
      lancamentoId: string | null;
    }) => api.controles.conciliarTransacao(transacaoId, lancamentoId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["controles", "transacoes"] });
    },
  });
}

export function useContasPagarReceber() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["controles", "pagar-receber", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedControles(empresa);
      return api.controles.listarContasPagarReceber();
    },
    enabled: !!empresa,
  });
}

export function useAdicionarContaPagarReceber() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (conta: ContaPagarReceber) =>
      api.controles.adicionarContaPagarReceber(conta),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["controles"] });
    },
  });
}

export function useAtualizarContaPagarReceber() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (conta: ContaPagarReceber) =>
      api.controles.atualizarContaPagarReceber(conta),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["controles"] });
    },
  });
}

export function useRemoverContaPagarReceber() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.controles.removerContaPagarReceber(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["controles"] });
    },
  });
}

export function useMarcarContaPaga() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, pagoEm }: { id: string; pagoEm: string }) =>
      api.controles.marcarContaPaga(id, pagoEm),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["controles"] });
    },
  });
}

export function useFluxoCaixa(dias = 90) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["controles", "fluxo-caixa", empresa?.cnpj, dias],
    queryFn: async () => {
      if (empresa) await garantirSeedControles(empresa);
      return api.controles.fluxoCaixa(dias);
    },
    enabled: !!empresa,
  });
}
