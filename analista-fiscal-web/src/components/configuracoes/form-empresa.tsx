"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Save } from "lucide-react";
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
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  anexoSimplesSchema,
  regimeTributarioSchema,
  type Empresa,
} from "@/lib/schemas/empresa";
import { formatarCNPJ } from "@/lib/format/cnpj";

const UFs = [
  "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
  "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
  "RO", "RR", "RS", "SC", "SE", "SP", "TO",
] as const;

const REGIME_LABEL: Record<z.infer<typeof regimeTributarioSchema>, string> = {
  MEI: "MEI",
  SIMPLES_NACIONAL: "Simples Nacional",
  LUCRO_PRESUMIDO: "Lucro Presumido",
  LUCRO_REAL: "Lucro Real",
};

const ANEXO_LABEL: Record<z.infer<typeof anexoSimplesSchema>, string> = {
  I: "Anexo I — Comércio",
  II: "Anexo II — Indústria",
  III: "Anexo III — Serviços (Fator R alto)",
  IV: "Anexo IV — Serviços específicos",
  V: "Anexo V — Serviços (Fator R baixo)",
};

const formSchema = z.object({
  razaoSocial: z.string().min(3, "Mínimo 3 caracteres"),
  nomeFantasia: z.string().optional(),
  regime: regimeTributarioSchema,
  anexoSimples: anexoSimplesSchema.optional(),
  uf: z.enum(UFs),
  municipio: z.string().min(2, "Informe o município"),
  inscricaoEstadual: z.string().optional(),
  inscricaoMunicipal: z.string().optional(),
  faturamento12m: z.coerce.number().min(0, "Valor inválido"),
});

type FormInput = z.infer<typeof formSchema>;

export function FormEmpresa({ empresa }: { empresa: Empresa }) {
  const { salvarEmpresa } = useEmpresaAtual();

  const form = useForm<FormInput>({
    resolver: zodResolver(formSchema),
    mode: "onTouched",
    defaultValues: {
      razaoSocial: empresa.razaoSocial,
      nomeFantasia: empresa.nomeFantasia ?? "",
      regime: empresa.regime,
      anexoSimples: empresa.anexoSimples,
      uf: (UFs.includes(empresa.uf as (typeof UFs)[number])
        ? (empresa.uf as (typeof UFs)[number])
        : "SP"),
      municipio: empresa.municipio,
      inscricaoEstadual: empresa.inscricaoEstadual ?? "",
      inscricaoMunicipal: empresa.inscricaoMunicipal ?? "",
      faturamento12m: empresa.faturamento12m,
    },
  });

  const regime = form.watch("regime");

  React.useEffect(() => {
    if (regime !== "SIMPLES_NACIONAL") {
      form.setValue("anexoSimples", undefined);
    } else if (!form.getValues("anexoSimples")) {
      form.setValue("anexoSimples", "III");
    }
  }, [regime, form]);

  async function aoSalvar(input: FormInput) {
    const atualizada: Empresa = {
      ...empresa,
      razaoSocial: input.razaoSocial.trim(),
      nomeFantasia: input.nomeFantasia?.trim() || undefined,
      regime: input.regime,
      anexoSimples:
        input.regime === "SIMPLES_NACIONAL" ? input.anexoSimples : undefined,
      uf: input.uf,
      municipio: input.municipio.trim(),
      inscricaoEstadual: input.inscricaoEstadual?.trim() || undefined,
      inscricaoMunicipal: input.inscricaoMunicipal?.trim() || undefined,
      faturamento12m: input.faturamento12m,
    };
    try {
      await salvarEmpresa(atualizada);
      toast.success("Cadastro atualizado", {
        description: "As novas informações já estão valendo nos cálculos.",
      });
      form.reset(input);
    } catch {
      toast.error("Não foi possível salvar agora.");
    }
  }

  return (
    <form
      onSubmit={form.handleSubmit(aoSalvar)}
      className="flex flex-col gap-5"
    >
      <Secao titulo="Identificação">
        <Campo
          label="CNPJ"
          erro={undefined}
          ajuda="O CNPJ não pode ser alterado por aqui — recadastre a empresa se mudou."
        >
          <Input
            value={formatarCNPJ(empresa.cnpj)}
            readOnly
            disabled
            className="mono"
          />
        </Campo>
        <Campo
          label="Razão social"
          erro={form.formState.errors.razaoSocial?.message}
        >
          <Input {...form.register("razaoSocial")} />
        </Campo>
        <Campo label="Nome fantasia (opcional)" erro={undefined}>
          <Input
            {...form.register("nomeFantasia")}
            placeholder="Como sua empresa é conhecida"
          />
        </Campo>
      </Secao>

      <Secao titulo="Regime tributário">
        <Campo label="Regime" erro={form.formState.errors.regime?.message}>
          <Select
            value={form.watch("regime")}
            onValueChange={(v) =>
              form.setValue(
                "regime",
                v as z.infer<typeof regimeTributarioSchema>,
                { shouldDirty: true, shouldValidate: true }
              )
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecione" />
            </SelectTrigger>
            <SelectContent>
              {(
                Object.keys(REGIME_LABEL) as Array<
                  keyof typeof REGIME_LABEL
                >
              ).map((r) => (
                <SelectItem key={r} value={r}>
                  {REGIME_LABEL[r]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Campo>

        {regime === "SIMPLES_NACIONAL" ? (
          <Campo
            label="Anexo do Simples"
            erro={form.formState.errors.anexoSimples?.message}
          >
            <Select
              value={form.watch("anexoSimples") ?? ""}
              onValueChange={(v) =>
                form.setValue(
                  "anexoSimples",
                  v as z.infer<typeof anexoSimplesSchema>,
                  { shouldDirty: true, shouldValidate: true }
                )
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecione o anexo" />
              </SelectTrigger>
              <SelectContent>
                {(
                  Object.keys(ANEXO_LABEL) as Array<
                    keyof typeof ANEXO_LABEL
                  >
                ).map((a) => (
                  <SelectItem key={a} value={a}>
                    {ANEXO_LABEL[a]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Campo>
        ) : null}

        <Campo
          label="Faturamento dos últimos 12 meses (R$)"
          erro={form.formState.errors.faturamento12m?.message}
          ajuda="Usado pra calcular alíquota efetiva do DAS e enquadramento."
        >
          <Input
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0"
            className="mono"
            {...form.register("faturamento12m")}
          />
        </Campo>
      </Secao>

      <Secao titulo="Endereço fiscal">
        <div className="grid grid-cols-1 md:grid-cols-[120px_1fr] gap-3">
          <Campo label="UF" erro={form.formState.errors.uf?.message}>
            <Select
              value={form.watch("uf")}
              onValueChange={(v) =>
                form.setValue("uf", v as (typeof UFs)[number], {
                  shouldDirty: true,
                  shouldValidate: true,
                })
              }
            >
              <SelectTrigger className="mono">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {UFs.map((uf) => (
                  <SelectItem key={uf} value={uf} className="mono">
                    {uf}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Campo>
          <Campo
            label="Município"
            erro={form.formState.errors.municipio?.message}
          >
            <Input {...form.register("municipio")} />
          </Campo>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Campo label="Inscrição Estadual (opcional)" erro={undefined}>
            <Input
              {...form.register("inscricaoEstadual")}
              className="mono"
              placeholder="Sem IE"
            />
          </Campo>
          <Campo label="Inscrição Municipal (opcional)" erro={undefined}>
            <Input
              {...form.register("inscricaoMunicipal")}
              className="mono"
              placeholder="Sem IM"
            />
          </Campo>
        </div>
      </Secao>

      <div className="flex items-center justify-end gap-2 pt-2">
        <Button
          type="submit"
          disabled={form.formState.isSubmitting || !form.formState.isDirty}
        >
          <Save className="size-4" />
          {form.formState.isSubmitting ? "Salvando..." : "Salvar alterações"}
        </Button>
      </div>
    </form>
  );
}

function Secao({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
        {titulo}
      </span>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  );
}

function Campo({
  label,
  erro,
  ajuda,
  children,
}: {
  label: string;
  erro?: string;
  ajuda?: string;
  children: React.ReactNode;
}) {
  const id = React.useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div id={id}>{children}</div>
      {erro ? (
        <p className="text-xs text-[var(--color-red)]">{erro}</p>
      ) : ajuda ? (
        <p className="text-[11px] text-[var(--color-txt-3)]">{ajuda}</p>
      ) : null}
    </div>
  );
}
