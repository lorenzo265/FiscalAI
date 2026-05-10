"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Send,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { PessoalSubnav } from "@/components/pessoal/pessoal-subnav";
import { AvatarFuncionario } from "@/components/pessoal/avatar-funcionario";
import {
  useFuncionarios,
  useGerarHoleritesDoMes,
  useHoleritesDoMes,
  useTransmitirEventosDoMes,
} from "@/hooks/use-pessoal";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  TIPO_CONTRATO_LABEL,
  type Funcionario,
  type Holerite,
} from "@/lib/schemas/pessoal";
import { formatarMesAnoBR } from "@/lib/format/data";

export default function FolhaMensalPage() {
  const params = useParams<{ ano: string; mes: string }>();
  const router = useRouter();
  const ano = Number(params?.ano ?? new Date().getFullYear());
  const mes = Number(params?.mes ?? new Date().getMonth() + 1);
  const competencia = `${ano}-${String(mes).padStart(2, "0")}-01`;

  const { empresa } = useEmpresaAtual();
  const {
    data: holerites,
    isLoading,
    isError,
    refetch,
  } = useHoleritesDoMes(ano, mes);
  const { data: funcionarios } = useFuncionarios();
  const gerar = useGerarHoleritesDoMes();
  const transmitir = useTransmitirEventosDoMes();

  const [transmitindo, setTransmitindo] = React.useState(false);

  const totais = React.useMemo(() => {
    const lista = holerites ?? [];
    return {
      bruto: lista.reduce((s, h) => s + h.totalProventos, 0),
      liquido: lista.reduce((s, h) => s + h.totalLiquido, 0),
      descontos: lista.reduce((s, h) => s + h.totalDescontos, 0),
      inssEmpresa: lista.reduce((s, h) => s + h.inssEmpresa, 0),
      fgts: lista.reduce((s, h) => s + h.fgts, 0),
    };
  }, [holerites]);

  function trocarMes(novoMes: string) {
    router.push(`/pessoal/folha/${ano}/${novoMes}`);
  }
  function trocarAno(novoAno: string) {
    router.push(`/pessoal/folha/${novoAno}/${mes}`);
  }

  async function gerarTodosPDFs() {
    if (!empresa || !holerites || holerites.length === 0) return;
    const toastId = toast.loading("Gerando holerites em PDF...");
    const { gerarPdfHolerite, nomeArquivoHolerite } = await import(
      "@/lib/pdf/holerite"
    );
    let ok = 0;
    for (const holerite of holerites) {
      const funcionario = funcionarios?.find(
        (f) => f.id === holerite.funcionarioId
      );
      if (!funcionario) continue;
      try {
        const pdf = gerarPdfHolerite({ empresa, funcionario, holerite });
        pdf.save(nomeArquivoHolerite(holerite));
        ok++;
        await new Promise((r) => setTimeout(r, 250));
      } catch (e) {
        console.error("Erro ao gerar holerite:", e);
      }
    }
    toast.success(`${ok} holerite${ok === 1 ? "" : "s"} gerado${ok === 1 ? "" : "s"}`, {
      id: toastId,
    });
  }

  async function transmitirEsocial() {
    setTransmitindo(true);
    try {
      const { transmitidos } = await transmitir.mutateAsync({ ano, mes });
      if (transmitidos === 0) {
        toast.info("Nenhum evento pendente para transmitir.");
      } else {
        toast.success(
          `${transmitidos} evento${transmitidos === 1 ? "" : "s"} transmitido${transmitidos === 1 ? "" : "s"}`,
          {
            description: "eSocial confirmou o recebimento de todos os recibos.",
          }
        );
      }
    } finally {
      setTransmitindo(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <Button asChild variant="ghost" className="self-start -ml-2">
          <Link href="/pessoal">
            <ArrowLeft className="size-4" /> Voltar para resumo
          </Link>
        </Button>
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div>
            <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
              Pessoal · Folha do mês
            </span>
            <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
              {formatarMesAnoBR(competencia)}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Select value={String(mes)} onValueChange={trocarMes}>
              <SelectTrigger className="w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <SelectItem key={m} value={String(m)}>
                    {formatarMesAnoBR(`${ano}-${String(m).padStart(2, "0")}-01`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={String(ano)} onValueChange={trocarAno}>
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[ano - 1, ano, ano + 1].map((a) => (
                  <SelectItem key={a} value={String(a)}>
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </header>

      <PessoalSubnav />

      {isLoading ? (
        <LoadingState titulo="Carregando folha..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !holerites || holerites.length === 0 ? (
        <EmptyState
          titulo="Folha ainda não foi gerada"
          descricao="Calcule os holerites com base nos funcionários ativos."
          icone={FileText}
          acao={
            <Button
              onClick={async () => {
                await gerar.mutateAsync({ ano, mes });
                toast.success("Holerites gerados");
              }}
              disabled={gerar.isPending}
            >
              {gerar.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileText className="size-4" />
              )}
              Gerar holerites
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              label="Total bruto"
              valor={<Moeda valor={totais.bruto} />}
              sub={`${holerites.length} holerites`}
            />
            <StatCard
              label="Total líquido"
              valor={<Moeda valor={totais.liquido} />}
              pill={{ tom: "ok", texto: "a pagar" }}
            />
            <StatCard
              label="Descontos"
              valor={<Moeda valor={totais.descontos} />}
              sub="INSS + IRRF + outros"
            />
            <StatCard
              label="Encargos patronais"
              valor={<Moeda valor={totais.inssEmpresa + totais.fgts} />}
              sub={`FGTS ${formatarBR(totais.fgts)} + INSS ${formatarBR(totais.inssEmpresa)}`}
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button onClick={gerarTodosPDFs}>
              <Download className="size-4" /> Gerar holerites em PDF
            </Button>
            <Button
              variant="outline"
              onClick={transmitirEsocial}
              disabled={transmitindo || transmitir.isPending}
            >
              {transmitindo || transmitir.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Send className="size-4" />
              )}
              Transmitir ao eSocial
            </Button>
            <Button
              variant="ghost"
              onClick={async () => {
                await gerar.mutateAsync({ ano, mes });
                toast.success("Folha recalculada");
              }}
              disabled={gerar.isPending}
            >
              Recalcular
            </Button>
          </div>

          <Card className="overflow-hidden">
            <ul
              className="divide-y"
              style={{ borderColor: "var(--color-line)" }}
            >
              {holerites.map((h) => (
                <LinhaHolerite
                  key={h.id}
                  holerite={h}
                  funcionario={funcionarios?.find((f) => f.id === h.funcionarioId)}
                  onBaixar={async () => {
                    if (!empresa) return;
                    const funcionario = funcionarios?.find(
                      (f) => f.id === h.funcionarioId
                    );
                    if (!funcionario) return;
                    const { gerarPdfHolerite, nomeArquivoHolerite } =
                      await import("@/lib/pdf/holerite");
                    const pdf = gerarPdfHolerite({ empresa, funcionario, holerite: h });
                    pdf.save(nomeArquivoHolerite(h));
                  }}
                />
              ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}

function LinhaHolerite({
  holerite,
  funcionario,
  onBaixar,
}: {
  holerite: Holerite;
  funcionario?: Funcionario;
  onBaixar: () => void;
}) {
  return (
    <li className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-card-2)] transition-colors">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        {funcionario ? (
          <AvatarFuncionario nome={funcionario.nome} seed={funcionario.avatarSeed} />
        ) : null}
        <div className="min-w-0">
          <span className="text-sm font-semibold text-[var(--color-txt)] truncate block">
            {holerite.funcionarioNome}
          </span>
          <span className="text-[11px] text-[var(--color-txt-3)] truncate block">
            {holerite.cargo}
            {funcionario
              ? ` · ${TIPO_CONTRATO_LABEL[funcionario.tipoContrato]}`
              : ""}
          </span>
        </div>
      </div>
      <div className="hidden md:flex items-center gap-3 text-[11px] text-[var(--color-txt-3)] mono">
        <span>
          P{" "}
          <span className="text-[var(--color-lime)]">
            <Moeda valor={holerite.totalProventos} />
          </span>
        </span>
        <span>
          D{" "}
          <span className="text-[var(--color-red)]">
            <Moeda valor={holerite.totalDescontos} />
          </span>
        </span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <Pill tom={holerite.status === "pago" ? "ok" : "info"}>
          {holerite.status === "pago" ? (
            <span className="flex items-center gap-1">
              <CheckCircle2 className="size-3" /> pago
            </span>
          ) : (
            "gerado"
          )}
        </Pill>
        <span className="mono text-base font-bold text-[var(--color-txt)]">
          <Moeda valor={holerite.totalLiquido} />
        </span>
        <Button variant="ghost" onClick={onBaixar} className="px-2" aria-label="Baixar holerite">
          <Download className="size-4" />
        </Button>
      </div>
    </li>
  );
}

function formatarBR(n: number): string {
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    style: "currency",
    currency: "BRL",
  }).format(n);
}
