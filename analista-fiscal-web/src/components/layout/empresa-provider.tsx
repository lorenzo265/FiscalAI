"use client";

import * as React from "react";
import type { Empresa } from "@/lib/schemas/empresa";
import { api, ApiError } from "@/lib/api-client";
import { isLogado } from "@/lib/auth";
import {
  getEmpresaIdAtiva,
  setEmpresaIdAtiva,
} from "@/lib/empresa-ativa";

interface EmpresaContextValue {
  empresa: Empresa | null;
  loading: boolean;
  refresh: () => Promise<void>;
  salvarEmpresa: (e: Empresa) => Promise<void>;
  resetar: () => Promise<void>;
}

const EmpresaContext = React.createContext<EmpresaContextValue | undefined>(
  undefined
);

/**
 * EmpresaProvider (Fase B — Auth & Empresa). HTTP real.
 *
 * No boot, se houver sessão (`isLogado()`), carrega `GET /v1/empresas`, escolhe
 * a empresa ativa (a salva em `getEmpresaIdAtiva()` ou a primeira) e persiste o
 * `empresa_id` ativo (usado pelos adapters de domínio para montar as rotas
 * `/v1/empresas/{id}/...`). Sem sessão, fica `loading=false` com `empresa=null`
 * — o `AuthGuard`/telas de auth cuidam do redirect.
 *
 * API pública do contexto preservada (`empresa`, `loading`, `refresh`,
 * `salvarEmpresa`, `resetar`) — telas e wizard dependem dela.
 */
export function EmpresaProvider({ children }: { children: React.ReactNode }) {
  const [empresa, setEmpresa] = React.useState<Empresa | null>(null);
  const [loading, setLoading] = React.useState(true);

  const carregar = React.useCallback(async () => {
    if (!isLogado()) {
      setEmpresa(null);
      setEmpresaIdAtiva(null);
      setLoading(false);
      return;
    }
    try {
      const lista = await api.empresa.listar();
      const salvaId = getEmpresaIdAtiva();
      const escolhida =
        (salvaId ? lista.find((e) => e.id === salvaId) : undefined) ?? lista[0];
      if (!escolhida) {
        setEmpresa(null);
        setEmpresaIdAtiva(null);
        return;
      }
      setEmpresaIdAtiva(escolhida.id);
      setEmpresa(escolhida);
    } catch (err) {
      // 401 já é tratado no fetchJson (limpa sessão + redirect). Demais erros:
      // não derruba o app — fica sem empresa e deixa o guard/telas decidirem.
      if (!(err instanceof ApiError) || err.status !== 401) {
        console.error("Falha ao carregar empresas:", err);
      }
      setEmpresa(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void carregar();
  }, [carregar]);

  /**
   * Atualiza a empresa ativa em memória + persiste o id ativo. A empresa em si
   * é criada/atualizada no backend (onboarding/criar). Não há endpoint de
   * UPDATE de empresa — edições locais (configurações) ficam só no contexto
   * até o próximo `refresh()` (gap registrado no handoff).
   */
  const salvarEmpresa = React.useCallback(async (e: Empresa) => {
    setEmpresaIdAtiva(e.id);
    setEmpresa(e);
  }, []);

  const resetar = React.useCallback(async () => {
    setEmpresaIdAtiva(null);
    setEmpresa(null);
  }, []);

  const value = React.useMemo<EmpresaContextValue>(
    () => ({ empresa, loading, refresh: carregar, salvarEmpresa, resetar }),
    [empresa, loading, carregar, salvarEmpresa, resetar]
  );

  return (
    <EmpresaContext.Provider value={value}>{children}</EmpresaContext.Provider>
  );
}

export function useEmpresaAtual(): EmpresaContextValue {
  const ctx = React.useContext(EmpresaContext);
  if (!ctx) {
    throw new Error("useEmpresaAtual deve ser usado dentro de EmpresaProvider");
  }
  return ctx;
}
