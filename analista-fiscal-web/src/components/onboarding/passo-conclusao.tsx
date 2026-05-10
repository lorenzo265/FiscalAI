"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, PartyPopper } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { Moeda } from "@/components/shared/moeda";
import { formatarDataBR } from "@/lib/format/data";
import { formatarPercentual } from "@/lib/format/numero";
import { calcularDAS, calcularProximoVencimentoDAS } from "@/lib/fiscal/calcula-das";
import type { Empresa, RegimeTributario } from "@/lib/schemas/empresa";
import { pseudoUuid } from "@/lib/mocks/utils";

export function PassoConclusao() {
  const router = useRouter();
  const dados = useOnboardingStore((s) => s.dadosReceita);
  const cnpj = useOnboardingStore((s) => s.cnpj);
  const regime = useOnboardingStore((s) => s.regime);
  const anexo = useOnboardingStore((s) => s.anexoSimples);
  const fat = useOnboardingStore((s) => s.faturamento12m);
  const certificadoNome = useOnboardingStore((s) => s.certificadoNome);
  const certificadoPulado = useOnboardingStore((s) => s.certificadoPulado);
  const bancosWizard = useOnboardingStore((s) => s.bancosConectados);
  const socios = useOnboardingStore((s) => s.socios);
  const reset = useOnboardingStore((s) => s.reset);
  const voltar = useOnboardingStore((s) => s.voltar);

  const { salvarEmpresa } = useEmpresaAtual();
  const [submetendo, setSubmetendo] = React.useState(false);

  const fatEstimado = fat > 0 ? fat : 850_000;
  const receitaMes = fatEstimado / 12;
  const calculo =
    regime === "SIMPLES_NACIONAL" && anexo
      ? calcularDAS({ rbt12: fatEstimado, receitaMes, anexo })
      : null;
  const vencimento = calcularProximoVencimentoDAS();

  async function finalizar() {
    if (!dados || !regime) {
      toast.error("Dados insuficientes. Volte e revise os passos anteriores.");
      return;
    }
    setSubmetendo(true);
    try {
      const empresa: Empresa = {
        id: pseudoUuid(),
        cnpj: dados.cnpj,
        razaoSocial: dados.razaoSocial,
        nomeFantasia: dados.nomeFantasia,
        regime,
        anexoSimples: regime === "SIMPLES_NACIONAL" && anexo ? anexo : undefined,
        setor: setorPorCnae(dados.cnaePrincipal.codigo),
        cnae: dados.cnaePrincipal.codigo,
        uf: dados.endereco.uf,
        municipio: dados.endereco.municipio,
        inscricaoEstadual: "ISENTO",
        inscricaoMunicipal: "98765432",
        faturamento12m: fatEstimado,
        socios,
        certificadoA1:
          certificadoNome && !certificadoPulado
            ? {
                nomeArquivo: certificadoNome,
                validade: "2027-05-08",
                mock: true,
              }
            : undefined,
        bancosConectados: bancosWizard.map((b) => ({
          id: b.id,
          banco: b.banco,
          apelido: b.apelido,
          saldo: b.saldo,
          ultimaSync: new Date().toISOString(),
        })),
        modulosAtivos: modulosPorRegime(regime),
        criadoEm: new Date().toISOString(),
      };

      await salvarEmpresa(empresa);
      reset();
      toast.success("Empresa cadastrada — bem-vindo ao FiscalAI.");
      router.push("/home");
    } catch (err) {
      console.error(err);
      toast.error("Não conseguimos salvar agora. Tente de novo.");
    } finally {
      setSubmetendo(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div
        className="rounded-md border p-5 flex items-start gap-3"
        style={{
          background: "var(--color-lime-d)",
          borderColor: "rgba(163, 255, 107, 0.32)",
        }}
      >
        <PartyPopper className="size-5 text-[var(--color-lime)] mt-0.5" />
        <div>
          <p className="text-sm font-bold text-[var(--color-txt)]">
            Quase lá, {dados?.razaoSocial ?? "—"}!
          </p>
          <p className="text-xs text-[var(--color-txt-2)] mt-1 leading-relaxed">
            {regime === "SIMPLES_NACIONAL" && anexo
              ? `Você é Simples Nacional Anexo ${anexo}, faturando aproximadamente ${new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(fatEstimado)} no ano. O FiscalAI já calculou seu próximo DAS.`
              : `Você é tributado por ${nomeRegime(regime)}. O FiscalAI vai acompanhar suas obrigações.`}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <ResumoCard
          label="CNPJ"
          conteudo={cnpj.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5")}
        />
        <ResumoCard
          label="Regime"
          conteudo={
            regime === "SIMPLES_NACIONAL" && anexo
              ? `Simples · Anexo ${anexo}`
              : nomeRegime(regime)
          }
        />
        <ResumoCard
          label="Sede"
          conteudo={`${dados?.endereco.municipio ?? "—"}/${dados?.endereco.uf ?? "—"}`}
        />
      </div>

      {calculo ? (
        <div
          className="rounded-md border p-4 flex flex-col gap-3"
          style={{
            background: "var(--color-card-2)",
            borderColor: "var(--color-line-2)",
          }}
        >
          <div className="flex items-center gap-2">
            <Pill tom="info">próximo DAS estimado</Pill>
            <span className="mono text-[10px] uppercase tracking-[0.16em] text-[var(--color-txt-3)]">
              vence em {formatarDataBR(vencimento)}
            </span>
          </div>
          <div className="flex items-end gap-3">
            <span className="mono text-3xl font-bold text-[var(--color-txt)]">
              <Moeda valor={calculo.valorDAS} />
            </span>
            <span className="mono text-xs text-[var(--color-txt-2)] mb-1.5">
              alíquota efetiva {formatarPercentual(calculo.aliquotaEfetiva)}
            </span>
          </div>
          <p className="text-xs text-[var(--color-txt-3)]">
            Estimativa baseada em receita mensal média. O cálculo final usa o
            faturamento real do mês.
          </p>
        </div>
      ) : null}

      {bancosWizard.length > 0 ? (
        <p className="text-xs text-[var(--color-txt-2)]">
          {bancosWizard.length} conta{bancosWizard.length === 1 ? "" : "s"} conectada
          {bancosWizard.length === 1 ? "" : "s"} via Open Finance.
        </p>
      ) : null}

      <div className="flex items-center justify-between pt-2">
        <Button variant="outline" onClick={voltar}>
          <ArrowLeft className="size-4" /> Voltar
        </Button>
        <Button onClick={finalizar} disabled={submetendo}>
          {submetendo ? "Finalizando..." : "Ir pro meu painel"}
          <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}

function ResumoCard({ label, conteudo }: { label: string; conteudo: string }) {
  return (
    <div
      className="rounded-md border p-3"
      style={{
        background: "var(--color-card-2)",
        borderColor: "var(--color-line-2)",
      }}
    >
      <p className="text-[10px] mono uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)]">
        {label}
      </p>
      <p className="text-sm text-[var(--color-txt)] mt-0.5">{conteudo}</p>
    </div>
  );
}

function nomeRegime(r: RegimeTributario | null): string {
  if (!r) return "—";
  if (r === "MEI") return "MEI";
  if (r === "SIMPLES_NACIONAL") return "Simples Nacional";
  if (r === "LUCRO_PRESUMIDO") return "Lucro Presumido";
  return "Lucro Real";
}

function setorPorCnae(cnae: string): "COMERCIO" | "INDUSTRIA" | "SERVICOS" | "MISTO" {
  const grupo = cnae.slice(0, 2);
  if (grupo.startsWith("47")) return "COMERCIO";
  if (grupo.startsWith("10") || grupo.startsWith("20") || grupo.startsWith("30"))
    return "INDUSTRIA";
  return "SERVICOS";
}

function modulosPorRegime(r: RegimeTributario): string[] {
  const base = ["home", "fiscal", "agenda", "compliance", "configuracoes"];
  if (r === "MEI") return [...base, "notas"];
  return [
    ...base,
    "notas",
    "contabil",
    "controles",
    "pessoal",
    "relatorios",
    "assistente",
  ];
}
