"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelarNota,
  adicionarCartaCorrecao,
  garantirSeedNotas,
  listarContrapartes,
  listarNotas,
  listarProdutos,
  manifestarNota,
  obterNota,
  salvarContraparte,
  salvarNota,
} from "@/lib/notas/db-service";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  manifestacao,
  type RegistrarManifestoInput,
} from "@/lib/api/manifestacao";
import type { Contraparte, NotaFiscal, StatusManifesto } from "@/lib/schemas/nota";

export function useNotas() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["notas", "list", empresa?.cnpj],
    queryFn: async () => {
      if (empresa) await garantirSeedNotas(empresa);
      return listarNotas();
    },
    enabled: !!empresa,
  });
}

export function useNota(chave: string | null | undefined) {
  return useQuery({
    queryKey: ["notas", "byChave", chave],
    queryFn: () => (chave ? obterNota(chave) : Promise.resolve(undefined)),
    enabled: !!chave,
  });
}

export function useSalvarNota() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (nota: NotaFiscal) => {
      await salvarNota(nota);
      return nota;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notas"] });
    },
  });
}

export function useCancelarNota() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ chave, motivo }: { chave: string; motivo: string }) => {
      await cancelarNota(chave, motivo);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notas"] });
    },
  });
}

export function useEmitirCartaCorrecao() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ chave, texto }: { chave: string; texto: string }) => {
      await adicionarCartaCorrecao(chave, texto);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notas"] });
    },
  });
}

export function useManifestar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      chave,
      manifesto,
    }: {
      chave: string;
      manifesto: StatusManifesto;
    }) => {
      await manifestarNota(chave, manifesto);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notas"] });
    },
  });
}

// ── MD-e: descoberta (DistribuiçãoDFe) + manifesto via backend real ──────────

/**
 * NF-e descobertas na Receita (DistribuiçãoDFe) contra o CNPJ da empresa.
 * `pendentes` (default true) traz só as que ainda não têm evento de manifesto.
 */
export function useDestinadas(pendentes = true) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["manifestacao", "destinadas", empresa?.cnpj, pendentes],
    queryFn: () => manifestacao.listarDestinadas({ pendentes }),
    enabled: !!empresa,
  });
}

/** Dispara a sincronização DistribuiçãoDFe (busca novas NF-e na Receita). */
export function useSincronizarDestinadas() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => manifestacao.sincronizar(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["manifestacao"] });
    },
  });
}

/**
 * Registra um evento de manifestação do destinatário no backend real (MD-e).
 * Distinto do `useManifestar` legado (que persiste o status só local/Dexie nas
 * notas importadas por XML); este fala com o módulo `manifestacao`.
 */
export function useRegistrarManifesto() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: RegistrarManifestoInput) =>
      manifestacao.registrar(input),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["manifestacao"] });
      void qc.invalidateQueries({ queryKey: ["notas"] });
    },
  });
}

export function useContrapartes() {
  return useQuery({
    queryKey: ["notas", "contrapartes"],
    queryFn: () => listarContrapartes(),
  });
}

export function useSalvarContraparte() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (c: Contraparte) => {
      await salvarContraparte(c);
      return c;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notas", "contrapartes"] });
    },
  });
}

export function useProdutosCatalogo() {
  return useQuery({
    queryKey: ["notas", "produtos"],
    queryFn: () => listarProdutos(),
  });
}
