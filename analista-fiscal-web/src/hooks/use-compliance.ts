"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { garantirSeedCompliance } from "@/lib/compliance/db-service";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function useCompliancePainel() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["compliance", "painel", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedCompliance(empresa);
      return api.compliance.painel();
    },
    enabled: !!empresa,
  });
}

export function useCertidoes() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["compliance", "certidoes", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedCompliance(empresa);
      return api.compliance.listarCertidoes();
    },
    enabled: !!empresa,
  });
}

export function useRenovarCertidao() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.compliance.renovarCertidao(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance"] });
    },
  });
}

export function useIntimacoes() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["compliance", "intimacoes", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedCompliance(empresa);
      return api.compliance.listarIntimacoes();
    },
    enabled: !!empresa,
  });
}

export function useMarcarIntimacaoLida() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.compliance.marcarIntimacaoLida(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance"] });
    },
  });
}

export function useEnviarIntimacaoAoContador() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.compliance.enviarAoContador(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance"] });
    },
  });
}

/** Mensagens reais do e-CAC (`GET /empresas/{id}/e-cac/mensagens`). */
export function useMensagensEcac() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["compliance", "ecac-mensagens", empresa?.cnpj],
    queryFn: () => api.compliance.listarMensagensEcac(),
    enabled: !!empresa,
  });
}

/** Dispara o sync com a Receita (`POST /empresas/{id}/e-cac/sync`). */
export function useSincronizarEcac() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.compliance.sincronizarEcac(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance"] });
    },
  });
}

export function useParcelamentos() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["compliance", "parcelamentos", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedCompliance(empresa);
      return api.compliance.listarParcelamentos();
    },
    enabled: !!empresa,
  });
}
