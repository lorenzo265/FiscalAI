"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  CATEGORIA_CONTA_LABEL,
  contaPagarReceberInputSchema,
  type CategoriaConta,
  type ContaPagarReceber,
  type ContaPagarReceberInput,
  type TipoContaPagarReceber,
} from "@/lib/schemas/controles";
import { pseudoUuid } from "@/lib/mocks/utils";

interface Props {
  tipo: TipoContaPagarReceber;
  aberto: boolean;
  onAbertoChange: (v: boolean) => void;
  conta?: ContaPagarReceber | null;
  onSalvar: (conta: ContaPagarReceber) => Promise<void> | void;
  salvando?: boolean;
}

const CATEGORIAS_PAGAR: CategoriaConta[] = [
  "fornecedor",
  "tributos",
  "folha",
  "aluguel",
  "energia",
  "telefonia_internet",
  "marketing",
  "servicos",
  "outros",
];

const CATEGORIAS_RECEBER: CategoriaConta[] = [
  "vendas",
  "servicos_prestados",
  "outros",
];

export function ContaFormDialog({
  tipo,
  aberto,
  onAbertoChange,
  conta,
  onSalvar,
  salvando,
}: Props) {
  const editando = !!conta;
  const tituloAcao = tipo === "pagar" ? "conta a pagar" : "conta a receber";

  const form = useForm<ContaPagarReceberInput>({
    resolver: zodResolver(contaPagarReceberInputSchema),
    defaultValues: defaultValues(tipo, conta),
  });

  React.useEffect(() => {
    if (aberto) {
      form.reset(defaultValues(tipo, conta));
    }
  }, [aberto, conta, form, tipo]);

  const categorias = tipo === "pagar" ? CATEGORIAS_PAGAR : CATEGORIAS_RECEBER;

  async function aoSubmeter(input: ContaPagarReceberInput) {
    const novo: ContaPagarReceber = {
      id: conta?.id ?? `${tipo}-${pseudoUuid()}`,
      tipo,
      descricao: input.descricao.trim(),
      contraparte: input.contraparte.trim(),
      valor: input.valor,
      vencimento: input.vencimento,
      categoria: input.categoria,
      status: conta?.status ?? "pendente",
      pagoEm: conta?.pagoEm,
      observacao: input.observacao?.trim() || undefined,
      criadoEm: conta?.criadoEm ?? new Date().toISOString(),
    };
    await onSalvar(novo);
  }

  return (
    <Dialog open={aberto} onOpenChange={onAbertoChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {editando ? `Editar ${tituloAcao}` : `Nova ${tituloAcao}`}
          </DialogTitle>
          <DialogDescription>
            {tipo === "pagar"
              ? "Cadastre uma despesa para acompanhar prazo, status e impacto no fluxo de caixa."
              : "Cadastre um valor que você espera receber para projetar entradas no caixa."}
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={form.handleSubmit(aoSubmeter)}
          className="grid grid-cols-1 md:grid-cols-2 gap-3"
        >
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <Label htmlFor="descricao">Descrição</Label>
            <Input
              id="descricao"
              placeholder={
                tipo === "pagar"
                  ? "Ex: Aluguel agosto"
                  : "Ex: Venda parcelada cliente Maria"
              }
              {...form.register("descricao")}
            />
            {form.formState.errors.descricao ? (
              <p className="text-xs text-[var(--color-danger)]">
                {form.formState.errors.descricao.message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="contraparte">
              {tipo === "pagar" ? "Fornecedor / contato" : "Cliente / contato"}
            </Label>
            <Input
              id="contraparte"
              placeholder={
                tipo === "pagar" ? "Ex: Distribuidora ABC" : "Ex: João da Silva"
              }
              {...form.register("contraparte")}
            />
            {form.formState.errors.contraparte ? (
              <p className="text-xs text-[var(--color-danger)]">
                {form.formState.errors.contraparte.message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="valor">Valor (R$)</Label>
            <Input
              id="valor"
              type="number"
              min="0.01"
              step="0.01"
              className="mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
              {...form.register("valor")}
            />
            {form.formState.errors.valor ? (
              <p className="text-xs text-[var(--color-danger)]">
                {form.formState.errors.valor.message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="vencimento">Vencimento</Label>
            <Input
              id="vencimento"
              type="date"
              className="mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
              {...form.register("vencimento")}
            />
            {form.formState.errors.vencimento ? (
              <p className="text-xs text-[var(--color-danger)]">
                {form.formState.errors.vencimento.message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="categoria">Categoria</Label>
            <Select
              value={form.watch("categoria")}
              onValueChange={(v) =>
                form.setValue("categoria", v as CategoriaConta, {
                  shouldValidate: true,
                })
              }
            >
              <SelectTrigger id="categoria">
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                {categorias.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {CATEGORIA_CONTA_LABEL[cat]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5 md:col-span-2">
            <Label htmlFor="observacao">Observação (opcional)</Label>
            <Input
              id="observacao"
              placeholder="Notas internas, número de boleto, etc."
              {...form.register("observacao")}
            />
          </div>

          <DialogFooter className="md:col-span-2 mt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onAbertoChange(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={salvando}>
              {editando ? "Salvar alterações" : "Cadastrar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function defaultValues(
  tipo: TipoContaPagarReceber,
  conta?: ContaPagarReceber | null
): ContaPagarReceberInput {
  if (conta) {
    return {
      tipo: conta.tipo,
      descricao: conta.descricao,
      contraparte: conta.contraparte,
      valor: conta.valor,
      vencimento: conta.vencimento,
      categoria: conta.categoria,
      observacao: conta.observacao,
    };
  }
  const hoje = new Date();
  hoje.setDate(hoje.getDate() + 7);
  return {
    tipo,
    descricao: "",
    contraparte: "",
    valor: 0,
    vencimento: hoje.toISOString().slice(0, 10),
    categoria: tipo === "pagar" ? "fornecedor" : "vendas",
    observacao: "",
  };
}
