"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import {
  garantirSeedAssistente,
} from "@/lib/assistente/db-service";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { garantirSeedCompliance } from "@/lib/compliance/db-service";
import { garantirSeedControles } from "@/lib/controles/db-service";
import { garantirSeedPessoal } from "@/lib/pessoal/db-service";

async function garantirSeedsParaContexto(
  empresa: import("@/lib/schemas/empresa").Empresa | null
) {
  if (!empresa) return;
  // Assistente depende de dados de outros módulos pra responder
  await garantirSeedAssistente(empresa);
  await garantirSeedControles(empresa);
  await garantirSeedPessoal(empresa);
  await garantirSeedCompliance(empresa);
}

export function useMensagensAssistente() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["assistente", "mensagens", empresa?.cnpj],
    queryFn: async () => {
      await garantirSeedsParaContexto(empresa);
      return api.assistente.listarMensagens();
    },
    enabled: !!empresa,
  });
}

export function useEnviarPergunta() {
  const { empresa } = useEmpresaAtual();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (pergunta: string) => {
      if (!empresa) throw new Error("empresa indisponível");
      await garantirSeedsParaContexto(empresa);
      return api.assistente.enviarPergunta(empresa, pergunta);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["assistente"] });
    },
  });
}

export function useLimparHistoricoAssistente() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.assistente.limparHistorico(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["assistente"] });
    },
  });
}
