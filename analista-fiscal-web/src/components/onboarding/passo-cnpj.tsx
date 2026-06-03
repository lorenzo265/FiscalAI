"use client";

import * as React from "react";
import { Search, CheckCircle2, Building2, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pill } from "@/components/shared/pill";
import { Ruler } from "@/components/blueprint/ruler";
import { mascaraCNPJ, validarCNPJ, apenasDigitos, formatarCNPJ } from "@/lib/format/cnpj";
import { api, ApiError } from "@/lib/api-client";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";

export function PassoCnpj() {
  const cnpj = useOnboardingStore((s) => s.cnpj);
  const dados = useOnboardingStore((s) => s.dadosReceita);
  const setCnpj = useOnboardingStore((s) => s.setCnpj);
  const setDados = useOnboardingStore((s) => s.setDadosReceita);
  const proximo = useOnboardingStore((s) => s.proximo);

  const [erro, setErro] = React.useState<string | null>(null);
  const [carregando, setCarregando] = React.useState(false);

  const valido = validarCNPJ(cnpj);

  async function buscar() {
    if (!valido) {
      setErro("CNPJ inválido. Confira os dígitos.");
      return;
    }
    setErro(null);
    setCarregando(true);
    try {
      const r = await api.empresa.lookupCnpj(apenasDigitos(cnpj));
      setDados(r);
    } catch (err) {
      if (err instanceof ApiError) {
        setErro("Não conseguimos consultar este CNPJ agora. Tente novamente.");
      } else {
        setErro("Erro inesperado.");
      }
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Label
          htmlFor="cnpj"
          className="text-[11px] mono uppercase tracking-[0.12em] font-bold text-[var(--color-ink-3)]"
        >
          CNPJ da empresa
        </Label>
        <div className="flex gap-2">
          <Input
            id="cnpj"
            inputMode="numeric"
            placeholder="00.000.000/0000-00"
            className="mono text-base"
            style={{ fontVariantNumeric: "tabular-nums" }}
            value={mascaraCNPJ(cnpj)}
            onChange={(e) => {
              setCnpj(apenasDigitos(e.target.value));
              setErro(null);
              setDados(null);
            }}
          />
          <Button onClick={buscar} disabled={!valido || carregando}>
            <Search className="size-4" />
            {carregando ? "Buscando..." : "Buscar"}
          </Button>
        </div>
        {erro ? (
          <p className="text-xs text-[var(--color-danger)]">{erro}</p>
        ) : null}
        <p className="text-[11px] text-[var(--color-ink-3)]">
          O CNPJ é consultado na Receita Federal. Não armazenamos dados fora
          deste navegador nesta demonstração.
        </p>
      </div>

      {/* resultado encontrado */}
      {dados ? (
        <div
          className="rounded-[var(--radius-md)] border flex flex-col gap-4 overflow-hidden"
          style={{
            background: "var(--color-green-wash)",
            borderColor: "var(--color-green)",
          }}
        >
          <div className="px-5 pt-4 pb-2 flex items-start gap-3">
            <div
              className="size-9 rounded-[var(--radius-sm)] grid place-items-center mt-0.5 border shrink-0"
              style={{
                background: "var(--color-green-wash)",
                borderColor: "var(--color-green)",
              }}
            >
              <CheckCircle2
                className="size-5"
                style={{ color: "var(--color-green)" }}
              />
            </div>
            <div className="flex-1">
              <p className="text-[11px] uppercase tracking-[0.14em] font-bold mono"
                 style={{ color: "var(--color-green)" }}>
                empresa encontrada
              </p>
              <h3 className="font-serif text-lg text-[var(--color-ink)] mt-1">
                {dados.razaoSocial}
              </h3>
              <p className="mono text-xs text-[var(--color-ink-2)] mt-0.5"
                 style={{ fontVariantNumeric: "tabular-nums" }}>
                <abbr title="Cadastro Nacional de Pessoas Jurídicas">{formatarCNPJ(dados.cnpj)}</abbr> · {dados.porte}
              </p>
            </div>
            <Pill tom="ok">{dados.situacao}</Pill>
          </div>

          <Ruler />

          <dl className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm px-5 pb-2">
            <ItemDl icone={<Building2 className="size-3.5" />} label="Atividade principal">
              <span className="text-[var(--color-ink)]">{dados.cnaePrincipal.descricao}</span>
            </ItemDl>
            <ItemDl icone={<MapPin className="size-3.5" />} label="Endereço">
              <span className="text-[var(--color-ink)]">
                {dados.endereco.logradouro}, {dados.endereco.numero} ·{" "}
                {dados.endereco.municipio}/{dados.endereco.uf}
              </span>
            </ItemDl>
          </dl>

          <div className="flex justify-end px-5 pb-5">
            <Button onClick={proximo}>Confirmar e continuar</Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ItemDl({
  icone,
  label,
  children,
}: {
  icone: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-ink-3)]">
        {icone}
        {label}
      </span>
      {children}
    </div>
  );
}
