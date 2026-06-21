"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
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
import { Framed } from "@/components/blueprint/framed";
import { Carimbo } from "@/components/blueprint/carimbo";
import { PessoalSubnav } from "@/components/pessoal/pessoal-subnav";
import { AvatarFuncionario } from "@/components/pessoal/avatar-funcionario";
import {
  useFuncionarios,
  useGerarHoleritesDoMes,
  useHoleritesDoMes,
  useTransmitirEventosDoMes,
} from "@/hooks/use-pessoal";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { mensagemAmigavelPessoal } from "@/lib/api/pessoal";
import {
  TIPO_CONTRATO_LABEL,
  type Funcionario,
  type Holerite,
} from "@/lib/schemas/pessoal";
import { formatarMesAnoBR } from "@/lib/format/data";
import { formatarMoeda } from "@/lib/format/moeda";
import { useCountUp } from "@/lib/motion/use-count-up";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

export default function FolhaMensalPage() {
  const params = useParams<{ ano: string; mes: string }>();
  const router = useRouter();
  const ano = Number(params?.ano ?? new Date().getFullYear());
  const mes = Number(params?.mes ?? new Date().getMonth() + 1);
  const competencia = `${ano}-${String(mes).padStart(2, "0")}-01`;
  const reduced = useReducedMotion();

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
  const folhaFechada =
    holerites &&
    holerites.length > 0 &&
    holerites.every((h) => h.status === "pago");

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
    toast.success(
      `${ok} holerite${ok === 1 ? "" : "s"} gerado${ok === 1 ? "" : "s"}`,
      { id: toastId }
    );
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
            description:
              "eSocial confirmou o recebimento de todos os recibos.",
          }
        );
      }
    } catch (err) {
      toast.error(mensagemAmigavelPessoal(err));
    } finally {
      setTransmitindo(false);
    }
  }

  /* ── número-herói: total líquido da folha ── */
  const liquidoCentavos = Math.round(totais.liquido * 100);
  const heroRaw = useCountUp(liquidoCentavos, {
    id: `folha:liquido:${competencia}`,
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);

  const containerV = reduced ? staticVariants : staggerChildren;
  const itemV = reduced ? staticVariants : revealChild;
  const pageV = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageV}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho + número-herói ── */}
      <motion.header
        className="flex flex-col gap-4"
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={itemV}>
          <Button asChild variant="ghost" className="self-start -ml-2" size="sm">
            <Link href="/pessoal">
              <ArrowLeft className="size-4" /> Voltar para resumo
            </Link>
          </Button>
        </motion.div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <motion.span
              variants={itemV}
              className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
            >
              Pessoal · Folha do mês
            </motion.span>
            <motion.h1
              variants={itemV}
              className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
            >
              {formatarMesAnoBR(competencia)}
            </motion.h1>
          </div>
          <motion.div variants={itemV} className="flex items-center gap-2 pt-5 md:pt-6">
            <Select value={String(mes)} onValueChange={trocarMes}>
              <SelectTrigger className="w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <SelectItem key={m} value={String(m)}>
                    {formatarMesAnoBR(
                      `${ano}-${String(m).padStart(2, "0")}-01`
                    )}
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
                    <span className="mono" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {a}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </motion.div>
        </div>

        {/* número-herói: total líquido da folha (só quando carregado) */}
        {!isLoading && holerites && holerites.length > 0 ? (
          <motion.div variants={itemV} className="flex flex-col gap-1">
            <span
              className="mono leading-none text-[var(--color-ink)] whitespace-nowrap"
              style={{
                fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
                fontWeight: 300,
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "-0.02em",
              }}
              aria-label={`Total líquido da folha: ${heroFormatado}`}
            >
              {heroFormatado}
            </span>
            <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
              total líquido da folha ·{" "}
              <span
                className="mono text-[var(--color-ink)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {holerites.length} holerite{holerites.length !== 1 ? "s" : ""}
              </span>
            </span>
          </motion.div>
        ) : null}
      </motion.header>

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

          {/* ── ações ── */}
          <div className="flex items-center gap-2 flex-wrap">
            <Button onClick={gerarTodosPDFs} size="sm">
              <Download className="size-4" /> Gerar holerites em PDF
            </Button>
            <Button
              variant="outline"
              size="sm"
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
              size="sm"
              onClick={async () => {
                await gerar.mutateAsync({ ano, mes });
                toast.success("Folha recalculada");
              }}
              disabled={gerar.isPending}
            >
              Recalcular
            </Button>
          </div>

          {/* ── tabela de holerites — marks=true é assinatura legítima (tela de print/holerite) ── */}
          <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
            <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)] flex items-center justify-between gap-2">
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
                Holerites do mês
              </h2>
              {folhaFechada ? (
                <Carimbo tom="green" sub="folha paga">
                  fechado
                </Carimbo>
              ) : null}
            </div>
            <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
              {holerites.map((h) => (
                <LinhaHolerite
                  key={h.id}
                  holerite={h}
                  funcionario={funcionarios?.find(
                    (f) => f.id === h.funcionarioId
                  )}
                  onBaixar={async () => {
                    if (!empresa) return;
                    const funcionario = funcionarios?.find(
                      (f) => f.id === h.funcionarioId
                    );
                    if (!funcionario) return;
                    const { gerarPdfHolerite, nomeArquivoHolerite } =
                      await import("@/lib/pdf/holerite");
                    const pdf = gerarPdfHolerite({
                      empresa,
                      funcionario,
                      holerite: h,
                    });
                    pdf.save(nomeArquivoHolerite(h));
                  }}
                />
              ))}
            </ul>
          </Framed>
        </>
      )}
    </motion.div>
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
    <li className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-paper-2)] transition-colors">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        {funcionario ? (
          <AvatarFuncionario
            nome={funcionario.nome}
            seed={funcionario.avatarSeed}
          />
        ) : null}
        <div className="min-w-0">
          <span className="text-sm font-semibold text-[var(--color-ink)] truncate block">
            {holerite.funcionarioNome}
          </span>
          <span className="text-[11px] text-[var(--color-ink-2)] truncate block">
            {holerite.cargo}
            {funcionario
              ? ` · ${TIPO_CONTRATO_LABEL[funcionario.tipoContrato]}`
              : ""}
          </span>
        </div>
      </div>
      <div className="hidden md:flex items-center gap-3 text-[11px] text-[var(--color-ink-3)] mono">
        <span>
          Prov{" "}
          <span
            className="text-[var(--color-green)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            <Moeda valor={holerite.totalProventos} />
          </span>
        </span>
        <span>
          Desc{" "}
          <span
            className="text-[var(--color-danger)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
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
        <span
          className="mono text-base font-bold text-[var(--color-ink)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <Moeda valor={holerite.totalLiquido} />
        </span>
        <Button
          variant="ghost"
          size="icon"
          onClick={onBaixar}
          className="size-8"
          aria-label="Baixar holerite"
        >
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
