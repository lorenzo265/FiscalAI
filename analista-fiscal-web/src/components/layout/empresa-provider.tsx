"use client";

import * as React from "react";
import type { Empresa } from "@/lib/schemas/empresa";
import { getDb } from "@/lib/db";
import { perfMark } from "@/lib/perf";

interface EmpresaContextValue {
  empresa: Empresa | null;
  loading: boolean;
  refresh: () => Promise<void>;
  salvarEmpresa: (e: Empresa) => Promise<void>;
  resetar: () => Promise<void>;
}

const EmpresaContext = React.createContext<EmpresaContextValue | undefined>(undefined);

const CACHE_KEY = "analista-fiscal:empresa-cache";
const CACHE_VERSION = 1;

interface CacheEnvelope {
  v: number;
  empresa: Empresa;
}

function lerCache(): Empresa | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CacheEnvelope;
    if (parsed.v !== CACHE_VERSION) return null;
    return parsed.empresa;
  } catch {
    return null;
  }
}

function gravarCache(empresa: Empresa | null): void {
  if (typeof window === "undefined") return;
  try {
    if (empresa) {
      const env: CacheEnvelope = { v: CACHE_VERSION, empresa };
      localStorage.setItem(CACHE_KEY, JSON.stringify(env));
    } else {
      localStorage.removeItem(CACHE_KEY);
    }
  } catch {
    /* ignore quota / private mode */
  }
}

export function EmpresaProvider({ children }: { children: React.ReactNode }) {
  const [empresa, setEmpresa] = React.useState<Empresa | null>(null);
  const [loading, setLoading] = React.useState(true);

  // Etapa 1 — síncrona no client mount: lê cache de localStorage.
  // Isso libera AuthGuard imediatamente quando há cache válido (boot ~5ms vs ~80ms).
  React.useEffect(() => {
    const stop = perfMark("empresa-provider:hydrate-cache");
    const cache = lerCache();
    if (cache) {
      setEmpresa(cache);
      setLoading(false);
      // Dispara seeds dos módulos em background — antecipa o trabalho
      // pra primeira navegação não pagar (~30-50ms cada).
      void import("@/lib/seeds/garantir-todos").then(({ garantirTodosSeeds }) =>
        garantirTodosSeeds(cache)
      );
      stop({ hit: true });
    } else {
      stop({ hit: false });
    }
  }, []);

  // Etapa 2 — assíncrona: revalida contra Dexie. Atualiza UI se estiver fora.
  const carregar = React.useCallback(async () => {
    const stop = perfMark("empresa-provider:carregar");
    try {
      if (process.env.NEXT_PUBLIC_PERF_BYPASS === "1") {
        const { criarEmpresaDemo } = await import("@/lib/stores/empresa-demo");
        const demo = criarEmpresaDemo();
        setEmpresa(demo);
        gravarCache(demo);
        stop({ bypass: true });
        return;
      }
      const db = getDb();
      const lista = await db.empresas.toArray();
      const next = lista[0] ?? null;
      setEmpresa((prev) => {
        if (
          prev &&
          next &&
          prev.id === next.id &&
          JSON.stringify(prev) === JSON.stringify(next)
        ) {
          return prev;
        }
        return next;
      });
      gravarCache(next);
      if (next) {
        void import("@/lib/seeds/garantir-todos").then(
          ({ garantirTodosSeeds }) => garantirTodosSeeds(next)
        );
      }
      stop({ encontrou: !!next });
    } catch (err) {
      console.error("Falha ao carregar empresa do Dexie:", err);
      stop({ erro: true });
    } finally {
      setLoading(false);
    }
  }, []);

  const salvarEmpresa = React.useCallback(async (e: Empresa) => {
    const db = getDb();
    await db.empresas.put(e);
    setEmpresa(e);
    gravarCache(e);
  }, []);

  const resetar = React.useCallback(async () => {
    try {
      const db = getDb();
      await db.transaction("rw", db.tables, async () => {
        await Promise.all(db.tables.map((t) => t.clear()));
      });
      Object.keys(localStorage)
        .filter((k) => k.startsWith("analista-fiscal:"))
        .forEach((k) => localStorage.removeItem(k));
    } catch (err) {
      console.error("Erro ao resetar dados:", err);
    }
    setEmpresa(null);
  }, []);

  React.useEffect(() => {
    void carregar();
  }, [carregar]);

  const value = React.useMemo<EmpresaContextValue>(
    () => ({ empresa, loading, refresh: carregar, salvarEmpresa, resetar }),
    [empresa, loading, carregar, salvarEmpresa, resetar]
  );

  return <EmpresaContext.Provider value={value}>{children}</EmpresaContext.Provider>;
}

export function useEmpresaAtual(): EmpresaContextValue {
  const ctx = React.useContext(EmpresaContext);
  if (!ctx) {
    throw new Error("useEmpresaAtual deve ser usado dentro de EmpresaProvider");
  }
  return ctx;
}
