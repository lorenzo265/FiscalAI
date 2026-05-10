"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { isLogado } from "@/lib/auth";
import { useEmpresaAtual } from "./empresa-provider";
import { LoadingState } from "@/components/shared/loading-state";
import { perfRecord } from "@/lib/perf";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { empresa, loading } = useEmpresaAtual();
  const [verificado, setVerificado] = React.useState(false);
  const mountedAtRef = React.useRef<number>(
    typeof performance !== "undefined" ? performance.now() : 0
  );

  React.useEffect(() => {
    if (process.env.NEXT_PUBLIC_PERF_BYPASS === "1") {
      perfRecord("auth-guard:verificado", mountedAtRef.current);
      setVerificado(true);
      return;
    }
    if (loading) return;
    if (!isLogado()) {
      router.replace("/login");
      return;
    }
    if (!empresa) {
      router.replace("/onboarding");
      return;
    }
    perfRecord("auth-guard:verificado", mountedAtRef.current);
    setVerificado(true);
  }, [loading, empresa, router]);

  if (loading || !verificado) {
    return (
      <div className="min-h-screen grid place-items-center">
        <LoadingState titulo="Carregando seu painel..." />
      </div>
    );
  }

  return <>{children}</>;
}
