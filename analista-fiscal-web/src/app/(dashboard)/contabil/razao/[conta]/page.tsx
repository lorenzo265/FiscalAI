"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Printer } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { OrigemPill } from "@/components/contabil/origem-pill";
import { useLancamentos } from "@/hooks/use-contabil";
import { montarRazao } from "@/lib/contabil/motor";
import { buscarConta } from "@/lib/mocks/seeds/plano-contas";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";

export default function RazaoContaPage() {
  const params = useParams<{ conta: string }>();
  const codigo = params?.conta ? decodeURIComponent(params.conta) : "";
  const conta = buscarConta(codigo);
  const { data, isLoading, isError, refetch } = useLancamentos();

  const linhas = React.useMemo(() => {
    if (!data || !conta) return [];
    return montarRazao(conta, data);
  }, [data, conta]);

  if (!conta) {
    return (
      <div className="flex flex-col gap-3 items-start">
        <p className="text-sm text-[var(--color-txt-2)]">
          Conta {codigo} não encontrada no plano de contas.
        </p>
        <Button asChild variant="outline">
          <Link href="/contabil">
            <ArrowLeft className="size-3.5" /> Voltar para o balancete
          </Link>
        </Button>
      </div>
    );
  }

  const totalDebitos = linhas.reduce((acc, l) => acc + l.debito, 0);
  const totalCreditos = linhas.reduce((acc, l) => acc + l.credito, 0);
  const saldoFinal = linhas.length > 0 ? linhas[linhas.length - 1]!.saldoApos : 0;

  return (
    <div className="flex flex-col gap-6 print:gap-3">
      <style>{`
        @media print {
          body { background: white !important; }
          .no-print { display: none !important; }
          .print\\:bg-white { background: white !important; }
          .print\\:text-black { color: black !important; }
        }
      `}</style>

      <div className="flex items-end justify-between gap-3 flex-wrap no-print">
        <div className="flex flex-col gap-1">
          <Link
            href="/contabil"
            className="text-[12px] text-[var(--color-txt-3)] hover:text-[var(--color-txt)] transition-colors flex items-center gap-1"
          >
            <ArrowLeft className="size-3" /> Voltar para o balancete
          </Link>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
            Razão analítico
          </span>
          <h1 className="text-[24px] md:text-[28px] font-extrabold tracking-tight text-[var(--color-txt)]">
            {conta.nome}
          </h1>
          <span className="mono text-xs text-[var(--color-txt-3)]">
            Código {conta.codigo} · natureza {conta.natureza.replace("_", " ")}
          </span>
        </div>
        <Button variant="outline" onClick={() => window.print()}>
          <Printer className="size-3.5" /> Imprimir
        </Button>
      </div>

      <div className="hidden print:block mb-2">
        <h1 className="text-2xl font-bold text-black">
          Razão analítico — {conta.nome}
        </h1>
        <p className="text-sm text-black/70">
          Código {conta.codigo} · Gerado em {formatarDataBR(new Date())}
        </p>
      </div>

      {isLoading ? (
        <LoadingState titulo="Carregando movimento..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : linhas.length === 0 ? (
        <EmptyState
          titulo="Sem movimento"
          descricao="Essa conta não tem lançamentos no período."
        />
      ) : (
        <Card className="overflow-hidden print:bg-white print:border-black/30">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-left border-b text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono print:text-black"
                  style={{ borderColor: "var(--color-line)" }}
                >
                  <th className="px-4 py-3">Data</th>
                  <th className="px-4 py-3">Histórico</th>
                  <th className="px-4 py-3">Conta contraparte</th>
                  <th className="px-4 py-3 text-right">Débito</th>
                  <th className="px-4 py-3 text-right">Crédito</th>
                  <th className="px-4 py-3 text-right">Saldo</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((l) => (
                  <tr
                    key={l.lancamento.id}
                    className="border-b transition-colors hover:bg-[var(--color-card-2)] print:hover:bg-white"
                    style={{ borderColor: "var(--color-line)" }}
                  >
                    <td className="px-4 py-3 align-top mono text-xs text-[var(--color-txt-2)] print:text-black">
                      {formatarDataBR(l.lancamento.data)}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <span className="text-[var(--color-txt)] print:text-black block">
                        {l.lancamento.historico}
                      </span>
                      <div className="mt-1 no-print">
                        <OrigemPill origem={l.lancamento.origem} />
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top text-[var(--color-txt-2)] print:text-black">
                      {l.contraparte}
                    </td>
                    <td className="px-4 py-3 align-top mono text-right">
                      <span
                        className={
                          l.debito > 0
                            ? "text-[var(--color-txt)] print:text-black"
                            : "text-[var(--color-txt-3)]"
                        }
                      >
                        {formatarMoeda(l.debito)}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-top mono text-right">
                      <span
                        className={
                          l.credito > 0
                            ? "text-[var(--color-txt)] print:text-black"
                            : "text-[var(--color-txt-3)]"
                        }
                      >
                        {formatarMoeda(l.credito)}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-top mono text-right font-bold text-[var(--color-txt)] print:text-black">
                      {formatarMoeda(l.saldoApos)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr
                  className="border-t bg-[var(--color-card-2)]/50 print:bg-white"
                  style={{ borderColor: "var(--color-line-2)" }}
                >
                  <td colSpan={3} className="px-4 py-3 text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono print:text-black">
                    Totais do período
                  </td>
                  <td className="px-4 py-3 mono text-right font-bold text-[var(--color-txt)] print:text-black">
                    {formatarMoeda(totalDebitos)}
                  </td>
                  <td className="px-4 py-3 mono text-right font-bold text-[var(--color-txt)] print:text-black">
                    {formatarMoeda(totalCreditos)}
                  </td>
                  <td className="px-4 py-3 mono text-right font-bold text-[var(--color-lime)] print:text-black">
                    {formatarMoeda(saldoFinal)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
