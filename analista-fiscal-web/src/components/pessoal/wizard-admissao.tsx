"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Check, ShieldCheck } from "lucide-react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Pill } from "@/components/shared/pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { Carimbo } from "@/components/blueprint/carimbo";
import { useAdicionarFuncionario } from "@/hooks/use-pessoal";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  funcionarioInputSchema,
  type FuncionarioInput,
} from "@/lib/schemas/pessoal";
import { mascaraCPF, validarCPF } from "@/lib/format/cpf";
import { formatarMoeda } from "@/lib/format/moeda";
import { pseudoUuid } from "@/lib/mocks/utils";
import { cn } from "@/lib/utils";

const PASSOS = [
  { titulo: "Dados pessoais", descricao: "Informações de identificação." },
  { titulo: "Contrato", descricao: "Como ele(a) vai trabalhar com a empresa." },
  { titulo: "Vínculo", descricao: "Cargo, salário, jornada." },
];

export function WizardAdmissao() {
  const router = useRouter();
  const { empresa } = useEmpresaAtual();
  const adicionar = useAdicionarFuncionario();
  const [passo, setPasso] = React.useState(0);
  const [admitido, setAdmitido] = React.useState(false);

  const form = useForm<FuncionarioInput>({
    resolver: zodResolver(funcionarioInputSchema),
    mode: "onTouched",
    defaultValues: {
      nome: "",
      cpf: "",
      email: "",
      telefone: "",
      dataNascimento: "",
      genero: "F",
      cargo: "",
      setor: "",
      tipoContrato: "CLT",
      jornadaSemanal: 44,
      salario: 0,
      dataAdmissao: new Date().toISOString().slice(0, 10),
    },
  });

  async function aoSalvar(input: FuncionarioInput) {
    if (!empresa) return;
    if (!validarCPF(input.cpf)) {
      form.setError("cpf", { message: "CPF inválido" });
      setPasso(0);
      return;
    }
    const id = `func-${empresa.id}-${pseudoUuid().slice(0, 8)}`;
    const cpfLimpo = input.cpf.replace(/\D/g, "");
    await adicionar.mutateAsync({
      id,
      nome: input.nome.trim(),
      cpf: cpfLimpo,
      email: input.email?.trim() || undefined,
      telefone: input.telefone?.trim() || undefined,
      dataNascimento: input.dataNascimento,
      genero: input.genero,
      cargo: input.cargo.trim(),
      setor: input.setor?.trim() || undefined,
      tipoContrato: input.tipoContrato,
      jornadaSemanal: input.jornadaSemanal,
      salario: input.salario,
      dataAdmissao: input.dataAdmissao,
      status: "ativo",
      avatarSeed: cpfLimpo,
      pisPasep: cpfLimpo,
    });
    setAdmitido(true);
    toast.success("Admissão registrada", {
      description:
        "Evento eSocial S-2200 (admissão) gerado. A transmissão ocorre após habilitar o certificado digital.",
    });
    setTimeout(() => router.push("/pessoal/funcionarios"), 1200);
  }

  async function avancar() {
    const camposPorPasso: Array<Array<keyof FuncionarioInput>> = [
      ["nome", "cpf", "dataNascimento", "genero"],
      ["tipoContrato", "dataAdmissao"],
      ["cargo", "salario", "jornadaSemanal"],
    ];
    const ok = await form.trigger(camposPorPasso[passo] ?? [], {
      shouldFocus: true,
    });
    if (!ok) return;
    if (passo < PASSOS.length - 1) {
      setPasso((p) => p + 1);
    } else {
      await form.handleSubmit(aoSalvar)();
    }
  }

  function voltar() {
    if (passo === 0) {
      router.push("/pessoal/funcionarios");
    } else {
      setPasso((p) => p - 1);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <header className="flex flex-col gap-2">
        <Button asChild variant="ghost" className="self-start -ml-2" size="sm">
          <Link href="/pessoal/funcionarios">
            <ArrowLeft className="size-4" /> Voltar para funcionários
          </Link>
        </Button>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold">
          Pessoal · Admissão
        </span>
        <h1 className="font-[family-name:var(--font-serif)] text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight">
          Admitir funcionário
        </h1>
        <p className="text-sm text-[var(--color-ink-2)]">
          3 passos. Ao final, geramos o evento{" "}
          <abbr
            title="S-2200 — Cadastramento Inicial do Vínculo Trabalhista"
            className="mono text-[11px] no-underline"
          >
            S-2200
          </abbr>{" "}
          e enviamos ao eSocial automaticamente.
        </p>
      </header>

      <Stepper passo={passo} />

      <Framed marks tone="ink" surface="card" className="flex flex-col gap-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Fig n={passo + 1} titulo={PASSOS[passo]?.titulo} size="sm" />
            <p className="text-sm text-[var(--color-ink-2)] mt-1">
              {PASSOS[passo]?.descricao}
            </p>
          </div>
          {admitido ? (
            <Carimbo tom="green" sub="admitido">OK</Carimbo>
          ) : null}
        </div>

        <Ruler />

        {passo === 0 ? <PassoDadosPessoais form={form} /> : null}
        {passo === 1 ? <PassoContrato form={form} /> : null}
        {passo === 2 ? <PassoVinculo form={form} /> : null}

        <Ruler />

        <div
          className="flex items-center gap-2 px-3 py-2.5 rounded-[var(--radius-md)] text-xs"
          style={{
            background: "var(--color-paper-2)",
            color: "var(--color-ink-2)",
          }}
        >
          <ShieldCheck className="size-4 text-[var(--color-green)] shrink-0" />
          Os dados ficam só no seu navegador (modo demo). Em produção,
          criptografados em repouso e em trânsito.
        </div>

        <div className="flex items-center justify-between gap-2 flex-wrap">
          <Button variant="outline" onClick={voltar} size="sm">
            <ArrowLeft className="size-4" />{" "}
            {passo === 0 ? "Cancelar" : "Voltar"}
          </Button>
          <Button onClick={avancar} disabled={adicionar.isPending} size="sm">
            {passo === PASSOS.length - 1 ? (
              <>
                Concluir admissão <Check className="size-4" />
              </>
            ) : (
              <>
                Continuar <ArrowRight className="size-4" />
              </>
            )}
          </Button>
        </div>
      </Framed>
    </div>
  );
}

function Stepper({ passo }: { passo: number }) {
  return (
    <div className="flex items-center gap-2">
      {PASSOS.map((p, i) => {
        const ativo = i <= passo;
        const atual = i === passo;
        return (
          <div key={p.titulo} className="flex items-center gap-2 flex-1">
            <div
              className={cn(
                "size-7 rounded-[var(--radius-sm)] grid place-items-center text-[11px] mono font-bold border",
                ativo
                  ? "bg-[var(--color-green-wash)] text-[var(--color-green)] border-[var(--color-green)]"
                  : "bg-[var(--color-paper-2)] text-[var(--color-ink-3)] border-[var(--color-rule-2)]"
              )}
            >
              {i < passo ? <Check className="size-3.5" /> : i + 1}
            </div>
            <div
              className={cn(
                "h-px flex-1",
                ativo
                  ? "bg-[var(--color-green)]"
                  : "bg-[var(--color-rule)]"
              )}
            />
          </div>
        );
      })}
    </div>
  );
}

function PassoDadosPessoais({
  form,
}: {
  form: UseFormReturn<FuncionarioInput>;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div className="flex flex-col gap-1.5 md:col-span-2">
        <Label htmlFor="nome">Nome completo</Label>
        <Input
          id="nome"
          placeholder="Ex: Maria da Silva"
          {...form.register("nome")}
        />
        <ErroCampo erro={form.formState.errors.nome?.message} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cpf">CPF</Label>
        <Input
          id="cpf"
          inputMode="numeric"
          placeholder="000.000.000-00"
          className="mono"
          value={form.watch("cpf")}
          onChange={(e) => form.setValue("cpf", mascaraCPF(e.target.value))}
        />
        <ErroCampo erro={form.formState.errors.cpf?.message} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="dataNascimento">Data de nascimento</Label>
        <Input
          id="dataNascimento"
          type="date"
          className="mono"
          {...form.register("dataNascimento")}
        />
        <ErroCampo erro={form.formState.errors.dataNascimento?.message} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="genero">Gênero</Label>
        <Select
          value={form.watch("genero")}
          onValueChange={(v) =>
            form.setValue("genero", v as FuncionarioInput["genero"])
          }
        >
          <SelectTrigger id="genero">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="F">Feminino</SelectItem>
            <SelectItem value="M">Masculino</SelectItem>
            <SelectItem value="X">Prefiro não informar</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email">E-mail (opcional)</Label>
        <Input id="email" type="email" {...form.register("email")} />
        <ErroCampo erro={form.formState.errors.email?.message} />
      </div>
      <div className="flex flex-col gap-1.5 md:col-span-2">
        <Label htmlFor="telefone">Telefone (opcional)</Label>
        <Input
          id="telefone"
          placeholder="(11) 99999-9999"
          {...form.register("telefone")}
        />
      </div>
    </div>
  );
}

function PassoContrato({ form }: { form: UseFormReturn<FuncionarioInput> }) {
  const tipo = form.watch("tipoContrato");
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div className="flex flex-col gap-1.5 md:col-span-2">
        <Label>Tipo de contrato</Label>
        <div className="grid grid-cols-3 gap-2">
          {(["CLT", "PJ", "ESTAGIO"] as const).map((opt) => {
            const ativo = tipo === opt;
            return (
              <button
                key={opt}
                type="button"
                onClick={() => form.setValue("tipoContrato", opt)}
                className={cn(
                  "rounded-[var(--radius-md)] border p-3 text-left transition-colors",
                  ativo
                    ? "border-[var(--color-green)] bg-[var(--color-green-wash)]"
                    : "border-[var(--color-rule-2)] bg-[var(--color-paper-2)] hover:bg-[var(--color-paper)]"
                )}
              >
                <div className="text-sm font-semibold text-[var(--color-ink)] mono">
                  {opt === "CLT" ? "CLT" : opt === "PJ" ? "PJ" : "Estágio"}
                </div>
                <div className="text-[11px] text-[var(--color-ink-3)] mt-1">
                  {opt === "CLT"
                    ? "Encargos e holerite mensal"
                    : opt === "PJ"
                      ? "Sem encargos · contrato de prestação"
                      : "Bolsa-auxílio sem holerite"}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="dataAdmissao">Data de admissão</Label>
        <Input
          id="dataAdmissao"
          type="date"
          className="mono"
          {...form.register("dataAdmissao")}
        />
        <ErroCampo erro={form.formState.errors.dataAdmissao?.message} />
      </div>

      {tipo === "CLT" ? (
        <div
          className="rounded-[var(--radius-md)] border p-3 md:col-span-2 flex items-start gap-2.5 text-xs"
          style={{
            background: "var(--color-green-wash)",
            borderColor: "var(--color-green)",
            color: "var(--color-ink)",
          }}
        >
          <Pill tom="ok">CLT</Pill>
          <span>
            Vamos calcular INSS, IRRF, FGTS e gerar holerite todo mês. Eventos{" "}
            <abbr
              title="S-2200 — Cadastramento, S-1200 — Remuneração, S-1299 — Fechamento"
              className="mono text-[11px] no-underline"
            >
              S-2200, S-1200 e S-1299
            </abbr>{" "}
            vão pro eSocial automaticamente.
          </span>
        </div>
      ) : null}
      {tipo === "PJ" ? (
        <div
          className="rounded-[var(--radius-md)] border p-3 md:col-span-2 flex items-start gap-2.5 text-xs"
          style={{
            background: "var(--color-paper-2)",
            borderColor: "var(--color-ochre)",
            color: "var(--color-ink)",
          }}
        >
          <Pill tom="warn">PJ</Pill>
          <span>
            Sem encargos trabalhistas. Geramos um recibo mensal — o ISS fica
            por conta do prestador.
          </span>
        </div>
      ) : null}
    </div>
  );
}

function PassoVinculo({ form }: { form: UseFormReturn<FuncionarioInput> }) {
  const salario = form.watch("salario");
  const jornada = form.watch("jornadaSemanal");
  const tipo = form.watch("tipoContrato");
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div className="flex flex-col gap-1.5 md:col-span-2">
        <Label htmlFor="cargo">Cargo</Label>
        <Input
          id="cargo"
          placeholder="Ex: Atendente sênior"
          {...form.register("cargo")}
        />
        <ErroCampo erro={form.formState.errors.cargo?.message} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="setor">Setor (opcional)</Label>
        <Input
          id="setor"
          placeholder="Ex: Atendimento"
          {...form.register("setor")}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="jornadaSemanal">Jornada semanal (h)</Label>
        <Input
          id="jornadaSemanal"
          type="number"
          min={1}
          max={44}
          className="mono"
          {...form.register("jornadaSemanal")}
        />
        <ErroCampo erro={form.formState.errors.jornadaSemanal?.message} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="salario">
          {tipo === "PJ"
            ? "Honorários mensais (R$)"
            : tipo === "ESTAGIO"
              ? "Bolsa-auxílio (R$)"
              : "Salário base (R$)"}
        </Label>
        <Input
          id="salario"
          type="number"
          min="0"
          step="0.01"
          className="mono"
          {...form.register("salario")}
        />
        <ErroCampo erro={form.formState.errors.salario?.message} />
      </div>
      <div className="md:col-span-2">
        <Framed
          marks={false}
          tone="rule"
          surface="paper-2"
          className="flex flex-col md:flex-row md:items-center justify-between gap-3"
        >
          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] mono text-[var(--color-ink-3)] font-bold">
              Resumo do vínculo
            </p>
            <p
              className="text-sm text-[var(--color-ink-2)] mt-1 mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {jornada}h/sem ·{" "}
              {formatarMoeda(salario || 0)} ·{" "}
              {tipo === "CLT"
                ? "Holerite e encargos automáticos"
                : tipo === "PJ"
                  ? "Recibo mensal sem encargos"
                  : "Bolsa-auxílio mensal"}
            </p>
          </div>
        </Framed>
      </div>
    </div>
  );
}

function ErroCampo({ erro }: { erro?: string }) {
  if (!erro) return null;
  return (
    <p className="text-xs text-[var(--color-danger)]">{erro}</p>
  );
}
