"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/shared/error-state";

/**
 * Error boundary global do App Router (Marco 4 — pontas soltas).
 *
 * Captura erros não tratados em qualquer rota abaixo de `app/layout.tsx`
 * (render, hooks, fetch sem try/catch) e oferece UMA ação: tentar de novo
 * (`reset()` re-renderiza o segmento). Antes disto, um erro estourava a tela
 * inteira sem saída — agora o dono da PME vê uma mensagem clara em pt-BR.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Observabilidade: o erro vai pro console (e ao Sentry no client, se ligado).
    console.error("Erro de rota não tratado:", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] grid place-items-center">
      <ErrorState
        titulo="Algo deu errado nesta tela"
        descricao="Tivemos um problema ao carregar esta página. Tente de novo — se continuar, atualize a página ou volte mais tarde."
        onTentarNovamente={reset}
      />
    </div>
  );
}
