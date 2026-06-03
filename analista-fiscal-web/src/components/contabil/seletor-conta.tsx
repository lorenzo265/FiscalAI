"use client";

import * as React from "react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PLANO_CONTAS } from "@/lib/mocks/seeds/plano-contas";

const NATUREZA_LABEL: Record<string, string> = {
  ativo: "Ativo",
  passivo: "Passivo",
  patrimonio_liquido: "Patrimônio Líquido",
  receita: "Receita",
  despesa: "Despesa",
  resultado: "Resultado",
};

interface Props {
  valor: string;
  onSelecionar: (codigo: string) => void;
  somenteAnaliticas?: boolean;
  placeholder?: string;
  disabled?: boolean;
}

export function SeletorConta({
  valor,
  onSelecionar,
  somenteAnaliticas = true,
  placeholder = "Selecione uma conta",
  disabled,
}: Props) {
  const grupos = React.useMemo(() => {
    const filtradas = somenteAnaliticas
      ? PLANO_CONTAS.filter((c) => c.analitica)
      : PLANO_CONTAS;
    const out = new Map<string, typeof PLANO_CONTAS>();
    for (const c of filtradas) {
      const key = c.natureza;
      const arr = out.get(key) ?? [];
      arr.push(c);
      out.set(key, arr);
    }
    return Array.from(out.entries());
  }, [somenteAnaliticas]);

  return (
    <Select value={valor} onValueChange={onSelecionar} disabled={disabled}>
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className="max-h-[320px]">
        {grupos.map(([natureza, contas]) => (
          <SelectGroup key={natureza}>
            <SelectLabel className="capitalize mono text-[10px] tracking-[0.14em] uppercase text-[var(--color-ink-3)]">
              {NATUREZA_LABEL[natureza] ?? natureza.replace("_", " ")}
            </SelectLabel>
            {contas.map((c) => (
              <SelectItem key={c.codigo} value={c.codigo}>
                <abbr
                  title={`Código: ${c.codigo}`}
                  className="no-underline mono text-[11px] text-[var(--color-ink-2)] mr-2"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {c.codigo}
                </abbr>
                {c.nome}
              </SelectItem>
            ))}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  );
}
