"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Framed } from "@/components/blueprint/framed";
import { ConfiguracoesSubnav } from "@/components/configuracoes/configuracoes-subnav";
import { FormEmpresa } from "@/components/configuracoes/form-empresa";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export default function ConfiguracoesEmpresaPage() {
  const { empresa, loading } = useEmpresaAtual();

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Link
          href="/configuracoes"
          className="text-[11px] mono uppercase tracking-[0.12em] text-[var(--color-ink-3)] font-bold inline-flex items-center gap-1 hover:text-[var(--color-ink-2)] transition-colors"
        >
          <ArrowLeft className="size-3" />
          Configurações
        </Link>
        <h1 className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight mt-1">
          Dados da empresa
        </h1>
        <p className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1">
          Atualize razão social, regime tributário e endereço fiscal. As
          mudanças entram em vigor imediatamente nos cálculos.
        </p>
      </header>

      <ConfiguracoesSubnav />

      {loading ? (
        <LoadingState titulo="Carregando dados da empresa..." />
      ) : !empresa ? (
        <EmptyState
          titulo="Nenhuma empresa cadastrada"
          descricao="Faça o onboarding para começar a usar o painel."
          acao={
            <Button asChild>
              <Link href="/onboarding">Ir para o cadastro</Link>
            </Button>
          }
        />
      ) : (
        <Framed marks={false} tone="rule" surface="card">
          <FormEmpresa empresa={empresa} />
        </Framed>
      )}
    </div>
  );
}
