"use client";

/**
 * Hooks do COFRE DE CERTIFICADO A1 — fala com o backend via `@/lib/api/certificado`.
 *
 * `useCertificadoStatus` lê os metadados do cert ativo (ou null se não há);
 * `useSubirCertificado`/`useRemoverCertificado` mutam e invalidam o status.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  certificado,
  type SubirCertificadoInput,
} from "@/lib/api/certificado";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function useCertificadoStatus() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["certificado", "status", empresa?.cnpj],
    queryFn: () => certificado.status(),
    enabled: !!empresa,
  });
}

export function useSubirCertificado() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: SubirCertificadoInput) => certificado.subir(input),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["certificado"] });
    },
  });
}

export function useRemoverCertificado() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => certificado.remover(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["certificado"] });
    },
  });
}
