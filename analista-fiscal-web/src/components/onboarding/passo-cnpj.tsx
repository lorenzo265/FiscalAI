"use client";

import * as React from "react";
import { Search, CheckCircle2, Building2, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pill } from "@/components/shared/pill";
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
        <Label htmlFor="cnpj">CNPJ da empresa</Label>
        <div className="flex gap-2">
          <Input
            id="cnpj"
            inputMode="numeric"
            placeholder="00.000.000/0000-00"
            className="mono text-base"
            value={mascaraCNPJ(cnpj)}
            onChange={(e) => {
              setCnpj(apenasDigitos(e.target.value));
              setErro(null);
              setDados(null);
            }}
          />
          <Button onClick={buscar} disabled={!valido || carregando}>
            <Search className="size-4" />
            {carregando ? "Buscando..." : "Buscar dados"}
          </Button>
        </div>
        {erro ? (
          <p className="text-xs text-[var(--color-red)]">{erro}</p>
        ) : null}
        <p className="text-xs text-[var(--color-txt-3)]">
          Não compartilhamos esse CNPJ com ninguém. Tudo é processado localmente
          na demonstração.
        </p>
      </div>

      {dados ? (
        <div
          className="rounded-md border p-5 flex flex-col gap-4"
          style={{
            background: "var(--color-lime-d)",
            borderColor: "rgba(163, 255, 107, 0.32)",
          }}
        >
          <div className="flex items-start gap-3">
            <div
              className="size-9 rounded-md grid place-items-center mt-0.5"
              style={{ background: "rgba(163, 255, 107, 0.18)" }}
            >
              <CheckCircle2 className="size-5 text-[var(--color-lime)]" />
            </div>
            <div className="flex-1">
              <p className="text-[11px] uppercase tracking-[0.14em] font-bold text-[var(--color-lime)] mono">
                empresa encontrada
              </p>
              <h3 className="text-lg font-bold text-[var(--color-txt)] mt-1">
                {dados.razaoSocial}
              </h3>
              <p className="mono text-xs text-[var(--color-txt-2)] mt-0.5">
                {formatarCNPJ(dados.cnpj)} · {dados.porte}
              </p>
            </div>
            <Pill tom="ok">{dados.situacao}</Pill>
          </div>

          <dl className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <Item icone={<Building2 className="size-3.5" />} label="Atividade principal">
              <span className="text-[var(--color-txt)]">{dados.cnaePrincipal.descricao}</span>
            </Item>
            <Item icone={<MapPin className="size-3.5" />} label="Endereço">
              <span className="text-[var(--color-txt)]">
                {dados.endereco.logradouro}, {dados.endereco.numero} ·{" "}
                {dados.endereco.municipio}/{dados.endereco.uf}
              </span>
            </Item>
          </dl>

          <div className="flex justify-end">
            <Button onClick={proximo}>Confirmar dados e continuar</Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Item({
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
      <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)]">
        {icone}
        {label}
      </span>
      {children}
    </div>
  );
}
