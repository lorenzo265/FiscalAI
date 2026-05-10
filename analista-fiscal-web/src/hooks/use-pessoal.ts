"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { garantirSeedPessoal } from "@/lib/pessoal/db-service";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { gerarEventoAdmissaoMock } from "@/lib/mocks/pessoal";
import type {
  EventoEsocial,
  Funcionario,
  StatusEventoEsocial,
} from "@/lib/schemas/pessoal";

export function useFuncionarios() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["pessoal", "funcionarios", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedPessoal(empresa);
      return api.pessoal.listarFuncionarios();
    },
    enabled: !!empresa,
  });
}

export function useFuncionario(id: string) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["pessoal", "funcionarios", empresa?.cnpj, id],
    queryFn: async () => {
      if (empresa) await garantirSeedPessoal(empresa);
      const f = await api.pessoal.obterFuncionario(id);
      if (!f) throw new Error("Funcionário não encontrado");
      return f;
    },
    enabled: !!empresa && !!id,
  });
}

export function useAdicionarFuncionario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (funcionario: Funcionario) => {
      await api.pessoal.adicionarFuncionario(funcionario);
      const evento = gerarEventoAdmissaoMock(funcionario);
      await api.pessoal.adicionarEventoEsocial(evento);
      return { funcionario, evento };
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pessoal"] });
    },
  });
}

export function useHolerites() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["pessoal", "holerites", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedPessoal(empresa);
      return api.pessoal.listarHolerites();
    },
    enabled: !!empresa,
  });
}

export function useHoleritesDoMes(ano: number, mes: number) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["pessoal", "holerites", empresa?.cnpj, ano, mes],
    queryFn: async () => {
      if (empresa) await garantirSeedPessoal(empresa);
      return api.pessoal.listarHoleritesDoMes(ano, mes);
    },
    enabled: !!empresa && Number.isFinite(ano) && Number.isFinite(mes),
  });
}

export function useGerarHoleritesDoMes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ano, mes }: { ano: number; mes: number }) =>
      api.pessoal.gerarHoleritesDoMes(ano, mes),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pessoal"] });
    },
  });
}

export function useEventosEsocial() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["pessoal", "esocial", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedPessoal(empresa);
      return api.pessoal.listarEventosEsocial();
    },
    enabled: !!empresa,
  });
}

export function useReenviarEvento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (evento: EventoEsocial) => {
      // simula latência da transmissão
      await new Promise((r) => setTimeout(r, 1500));
      const status: StatusEventoEsocial = "transmitido";
      await api.pessoal.atualizarStatusEvento(evento.id, status, {
        recibo: `R-${Math.random().toString(36).slice(2, 10).toUpperCase()}`,
      });
      return { ...evento, status };
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pessoal"] });
    },
  });
}

export function useTransmitirEventosDoMes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ ano, mes }: { ano: number; mes: number }) => {
      await new Promise((r) => setTimeout(r, 3000));
      return api.pessoal.transmitirEventosDoMes(ano, mes);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pessoal"] });
    },
  });
}
