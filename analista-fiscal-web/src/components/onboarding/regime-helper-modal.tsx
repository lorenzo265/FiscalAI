"use client";

import * as React from "react";
import { HelpCircle, Sparkles } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Pill } from "@/components/shared/pill";
import type { RegimeTributario } from "@/lib/schemas/empresa";
import { formatarMoeda } from "@/lib/format/moeda";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSugerir: (regime: RegimeTributario, fat: number) => void;
}

type Atividade = "comercio" | "servicos" | "industria";

export function RegimeHelperModal({ open, onOpenChange, onSugerir }: Props) {
  const [faturamento, setFaturamento] = React.useState("60000");
  const [atividade, setAtividade] = React.useState<Atividade>("servicos");
  const [funcionarios, setFuncionarios] = React.useState("3");
  const [resultado, setResultado] = React.useState<{
    regime: RegimeTributario;
    explicacao: string;
  } | null>(null);

  function calcular() {
    const fat = Number(faturamento.replace(/\D/g, ""));
    const fatAnual = fat * 12;
    const func = Number(funcionarios) || 0;

    let regime: RegimeTributario = "SIMPLES_NACIONAL";
    let explicacao =
      "Empresas com faturamento até R$ 4,8 milhões por ano costumam ficar no Simples Nacional, que junta vários impostos em um só pagamento.";

    if (fatAnual <= 81_000 && func === 0 && atividade !== "industria") {
      regime = "MEI";
      explicacao =
        "Você fatura pouco e não tem funcionários. O MEI é o regime mais simples: imposto fixo mensal e uma única declaração no ano.";
    } else if (fatAnual > 4_800_000 && fatAnual <= 78_000_000) {
      regime = "LUCRO_PRESUMIDO";
      explicacao =
        "Acima do teto do Simples (R$ 4,8M/ano), o Lucro Presumido é geralmente a opção mais leve para serviços e comércio.";
    } else if (fatAnual > 78_000_000) {
      regime = "LUCRO_REAL";
      explicacao =
        "Acima de R$ 78M/ano, o Lucro Real passa a ser obrigatório.";
    }

    setResultado({ regime, explicacao });
  }

  function aceitar() {
    if (!resultado) return;
    const fatAnual = Number(faturamento.replace(/\D/g, "")) * 12;
    onSugerir(resultado.regime, fatAnual);
    onOpenChange(false);
    setResultado(null);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <HelpCircle className="size-5 text-[var(--color-lime)]" />
            Vamos descobrir juntos
          </DialogTitle>
          <DialogDescription>
            3 perguntas rápidas. Responda do jeito que conseguir — você pode
            ajustar depois.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fat">Quanto sua empresa fatura por mês?</Label>
            <div className="flex items-center gap-2">
              <span className="mono text-xs text-[var(--color-txt-3)]">R$</span>
              <Input
                id="fat"
                type="number"
                value={faturamento}
                onChange={(e) => setFaturamento(e.target.value)}
                className="mono"
              />
            </div>
            <p className="text-[10px] text-[var(--color-txt-3)] mono">
              Anualizado: {formatarMoeda(Number(faturamento) * 12)}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label>Tipo de atividade</Label>
            <RadioGroup
              value={atividade}
              onValueChange={(v) => setAtividade(v as Atividade)}
              className="grid grid-cols-3 gap-2"
            >
              {(["comercio", "servicos", "industria"] as Atividade[]).map((a) => (
                <label
                  key={a}
                  className="flex items-center gap-2 p-2.5 rounded-md border border-[var(--color-line-2)] cursor-pointer hover:bg-[var(--color-card-2)]"
                >
                  <RadioGroupItem value={a} id={`a-${a}`} />
                  <span className="text-sm capitalize">{a}</span>
                </label>
              ))}
            </RadioGroup>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="func">Quantos funcionários CLT?</Label>
            <Input
              id="func"
              type="number"
              value={funcionarios}
              onChange={(e) => setFuncionarios(e.target.value)}
              className="mono"
            />
          </div>

          {!resultado ? (
            <Button onClick={calcular}>
              <Sparkles className="size-4" />
              Sugerir o regime mais provável
            </Button>
          ) : (
            <div
              className="rounded-md border p-4 flex flex-col gap-2"
              style={{
                background: "var(--color-lime-d)",
                borderColor: "rgba(163, 255, 107, 0.32)",
              }}
            >
              <div className="flex items-center gap-2">
                <Pill tom="ok">recomendação</Pill>
                <span className="text-base font-bold text-[var(--color-txt)]">
                  {nomeRegime(resultado.regime)}
                </span>
              </div>
              <p className="text-sm text-[var(--color-txt-2)] leading-relaxed">
                {resultado.explicacao}
              </p>
              <div className="flex gap-2 mt-1">
                <Button onClick={aceitar} className="flex-1">
                  Aceitar e continuar
                </Button>
                <Button variant="outline" onClick={() => setResultado(null)}>
                  Refazer
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function nomeRegime(r: RegimeTributario): string {
  if (r === "MEI") return "MEI";
  if (r === "SIMPLES_NACIONAL") return "Simples Nacional";
  if (r === "LUCRO_PRESUMIDO") return "Lucro Presumido";
  return "Lucro Real";
}
