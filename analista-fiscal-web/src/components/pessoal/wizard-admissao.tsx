"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Check, ShieldCheck } from "lucide-react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
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
    const novo = await adicionar.mutateAsync({
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
    toast.success("Admissão registrada", {
      description: `Evento eSocial S-2200 transmitido com sucesso (recibo: ${
        novo.evento.recibo ?? "—"
      }).`,
    });
    router.push("/pessoal/funcionarios");
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
        <Button asChild variant="ghost" className="self-start -ml-2">
          <Link href="/pessoal/funcionarios">
            <ArrowLeft className="size-4" /> Voltar para funcionários
          </Link>
        </Button>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Pessoal · Admissão
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Admitir funcionário
        </h1>
        <p className="text-sm text-[var(--color-txt-2)]">
          3 passos. Ao final, geramos o evento <strong>S-2200</strong> e
          mandamos pro eSocial automaticamente.
        </p>
      </header>

      <Stepper passo={passo} />

      <Card
        className="p-7 flex flex-col gap-6 border"
        style={{
          background: "var(--color-card)",
          borderColor: "var(--color-line-2)",
        }}
      >
        <div>
          <h2 className="text-lg font-bold text-[var(--color-txt)]">
            {PASSOS[passo]?.titulo}
          </h2>
          <p className="text-sm text-[var(--color-txt-2)]">
            {PASSOS[passo]?.descricao}
          </p>
        </div>

        {passo === 0 ? <PassoDadosPessoais form={form} /> : null}
        {passo === 1 ? <PassoContrato form={form} /> : null}
        {passo === 2 ? <PassoVinculo form={form} /> : null}

        <div
          className="flex items-center gap-2 px-3 py-2.5 rounded-md text-xs"
          style={{
            background: "var(--color-card-2)",
            color: "var(--color-txt-2)",
          }}
        >
          <ShieldCheck className="size-4 text-[var(--color-lime)]" />
          Os dados ficam só no seu navegador (mock). Em produção, criptografados
          em repouso e em trânsito.
        </div>

        <div className="flex items-center justify-between gap-2 flex-wrap">
          <Button variant="outline" onClick={voltar}>
            <ArrowLeft className="size-4" />{" "}
            {passo === 0 ? "Cancelar" : "Voltar"}
          </Button>
          <Button onClick={avancar} disabled={adicionar.isPending}>
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
      </Card>
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
                "size-7 rounded-full grid place-items-center text-[11px] mono font-bold border",
                ativo
                  ? "bg-[var(--color-lime-d)] text-[var(--color-lime)] border-[rgba(163,255,107,0.32)]"
                  : "bg-[var(--color-card-2)] text-[var(--color-txt-3)] border-[var(--color-line-2)]"
              )}
            >
              {i < passo ? <Check className="size-3.5" /> : i + 1}
            </div>
            <div
              className={cn(
                "h-1 flex-1 rounded-full",
                ativo ? "bg-[var(--color-lime)]" : "bg-[var(--color-card-3)]",
                atual ? "shadow-[0_0_12px_rgba(163,255,107,0.4)]" : ""
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
        <Input id="nome" placeholder="Ex: Maria da Silva" {...form.register("nome")} />
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
        <Input id="telefone" placeholder="(11) 99999-9999" {...form.register("telefone")} />
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
                  "rounded-md border p-3 text-left transition-colors",
                  ativo
                    ? "border-[var(--color-lime)] bg-[var(--color-lime-d)]"
                    : "border-[var(--color-line-2)] bg-[var(--color-card-2)] hover:bg-[var(--color-card-3)]"
                )}
              >
                <div className="text-sm font-semibold text-[var(--color-txt)]">
                  {opt === "CLT"
                    ? "CLT"
                    : opt === "PJ"
                      ? "PJ"
                      : "Estágio"}
                </div>
                <div className="text-[11px] text-[var(--color-txt-3)] mt-1">
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
          className="rounded-md border p-3 md:col-span-2 flex items-start gap-2.5 text-xs"
          style={{
            background: "var(--color-blue-d)",
            borderColor: "rgba(77,142,255,0.22)",
            color: "var(--color-txt)",
          }}
        >
          <Pill tom="info">CLT</Pill>
          <span>
            Vamos calcular INSS, IRRF, FGTS e gerar holerite todo mês.
            Eventos S-2200, S-1200 e S-1299 vão pro eSocial automaticamente.
          </span>
        </div>
      ) : null}
      {tipo === "PJ" ? (
        <div
          className="rounded-md border p-3 md:col-span-2 flex items-start gap-2.5 text-xs"
          style={{
            background: "var(--color-amber-d)",
            borderColor: "rgba(255,184,77,0.22)",
            color: "var(--color-txt)",
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
        <Input id="cargo" placeholder="Ex: Atendente sênior" {...form.register("cargo")} />
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
        <Card className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-[var(--color-card-2)]">
          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] mono text-[var(--color-txt-3)] font-bold">
              Resumo do vínculo
            </p>
            <p className="text-sm text-[var(--color-txt-2)] mt-1">
              {jornada}h/sem · {formatarMoeda(salario || 0)} ·{" "}
              {tipo === "CLT"
                ? "Holerite e encargos automáticos"
                : tipo === "PJ"
                  ? "Recibo mensal sem encargos"
                  : "Bolsa-auxílio mensal"}
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}

function ErroCampo({ erro }: { erro?: string }) {
  if (!erro) return null;
  return <p className="text-xs text-[var(--color-red)]">{erro}</p>;
}
