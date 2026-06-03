"use client";

import * as React from "react";
import { Search, UserPlus, ArrowRight, Building2, User } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/shared/loading-state";
import { Pill } from "@/components/shared/pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { api } from "@/lib/api-client";
import { ApiError } from "@/lib/api-client";
import { mascaraCNPJ, formatarCNPJ, apenasDigitos } from "@/lib/format/cnpj";
import { mascaraCPF, formatarCPF } from "@/lib/format/cpf";
import { useNfWizardStore } from "@/lib/stores/nf-wizard-store";
import type { Contraparte } from "@/lib/schemas/nota";

export function PassoDestinatario() {
  const { contraparte, setContraparte, proximo } = useNfWizardStore();
  const [doc, setDoc] = React.useState("");
  const [carregando, setCarregando] = React.useState(false);
  const [modoCadastro, setModoCadastro] = React.useState(false);

  const documentoLimpo = apenasDigitos(doc);
  const tipo: "pj" | "pf" = documentoLimpo.length > 11 ? "pj" : "pf";

  const buscar = async () => {
    if (documentoLimpo.length !== 11 && documentoLimpo.length !== 14) {
      toast.error("Documento inválido", {
        description: "Informe um CNPJ (14 dígitos) ou CPF (11 dígitos).",
      });
      return;
    }
    setCarregando(true);
    try {
      const c = await api.notas.lookupContraparte(documentoLimpo);
      setContraparte(c);
      toast.success("Encontrado", { description: c.nome });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setModoCadastro(true);
        toast.info("Não cadastrado ainda", {
          description: "Preencha os dados para cadastrar inline.",
        });
      } else {
        toast.error("Falha na busca", {
          description: "Tente novamente em instantes.",
        });
      }
    } finally {
      setCarregando(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Framed marks tone="ink" surface="card" className="flex flex-col gap-4">
        <Fig n={1} titulo="Quem vai receber a nota?" />
        <Ruler />

        <div className="flex flex-col md:flex-row gap-2 items-end pt-1">
          <div className="flex-1 flex flex-col gap-1.5">
            <Label htmlFor="doc">CNPJ ou CPF</Label>
            <Input
              id="doc"
              value={tipo === "pj" ? mascaraCNPJ(doc) : mascaraCPF(doc)}
              onChange={(e) => setDoc(e.target.value)}
              placeholder="00.000.000/0000-00"
              className="mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
              autoFocus
            />
          </div>
          <Button onClick={buscar} disabled={carregando || !doc}>
            <Search className="size-3.5" />
            {carregando ? "Buscando..." : "Buscar"}
          </Button>
        </div>

        {carregando ? (
          <LoadingState titulo="Consultando registro..." />
        ) : contraparte ? (
          <ContraparteCard contraparte={contraparte} />
        ) : modoCadastro ? (
          <CadastrarInline
            documento={documentoLimpo}
            onSalvar={(c) => {
              setContraparte(c);
              setModoCadastro(false);
            }}
          />
        ) : null}

        <div
          className="flex justify-between items-center pt-2 border-t"
          style={{ borderColor: "var(--color-rule)" }}
        >
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setModoCadastro((v) => !v)}
          >
            <UserPlus className="size-3.5" />
            {modoCadastro ? "Voltar à busca" : "Cadastrar novo cliente"}
          </Button>
          <Button onClick={proximo} disabled={!contraparte} size="lg">
            Continuar <ArrowRight className="size-4" />
          </Button>
        </div>
      </Framed>
    </div>
  );
}

function ContraparteCard({ contraparte }: { contraparte: Contraparte }) {
  const Icon = contraparte.tipo === "pj" ? Building2 : User;
  return (
    <div
      className="rounded-[var(--radius-md)] border p-4 flex items-start gap-3"
      style={{
        background: "var(--color-green-wash)",
        borderColor: "var(--color-green)",
      }}
    >
      {/* ícone em fio técnico — sem quadradinho de fundo lavado */}
      <Icon
        className="size-5 shrink-0 mt-0.5"
        style={{ color: "var(--color-green)" }}
        aria-hidden
      />
      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-serif text-base text-[var(--color-ink)] truncate">
            {contraparte.nome}
          </span>
          <Pill tom="ok">encontrado</Pill>
        </div>
        <span
          className="mono text-xs text-[var(--color-ink-2)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {contraparte.tipo === "pj"
            ? formatarCNPJ(contraparte.documento)
            : formatarCPF(contraparte.documento)}
        </span>
        {contraparte.endereco ? (
          <span className="text-[12px] text-[var(--color-ink-3)] leading-snug">
            {contraparte.endereco.logradouro}, {contraparte.endereco.numero} ·{" "}
            {contraparte.endereco.municipio}/{contraparte.endereco.uf}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function CadastrarInline({
  documento,
  onSalvar,
}: {
  documento: string;
  onSalvar: (c: Contraparte) => void;
}) {
  const [nome, setNome] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [logradouro, setLogradouro] = React.useState("");
  const [numero, setNumero] = React.useState("");
  const [bairro, setBairro] = React.useState("");
  const [municipio, setMunicipio] = React.useState("");
  const [uf, setUf] = React.useState("");
  const [cep, setCep] = React.useState("");

  const tipo: "pj" | "pf" = documento.length > 11 ? "pj" : "pf";

  return (
    <div
      className="rounded-[var(--radius-md)] border p-4 flex flex-col gap-3"
      style={{
        background: "var(--color-paper-2)",
        borderColor: "var(--color-rule-2)",
      }}
    >
      <div className="flex items-center gap-2">
        <UserPlus className="size-4 text-[var(--color-ink-3)]" aria-hidden />
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
          Cadastro inline
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5 md:col-span-2">
          <Label>Razão social / Nome</Label>
          <Input value={nome} onChange={(e) => setNome(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>E-mail</Label>
          <Input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>CEP</Label>
          <Input
            value={cep}
            onChange={(e) => setCep(e.target.value)}
            className="mono"
            style={{ fontVariantNumeric: "tabular-nums" }}
          />
        </div>
        <div className="flex flex-col gap-1.5 md:col-span-2">
          <Label>Logradouro</Label>
          <Input
            value={logradouro}
            onChange={(e) => setLogradouro(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Número</Label>
          <Input
            value={numero}
            onChange={(e) => setNumero(e.target.value)}
            className="mono"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Bairro</Label>
          <Input value={bairro} onChange={(e) => setBairro(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Município</Label>
          <Input
            value={municipio}
            onChange={(e) => setMunicipio(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>UF</Label>
          <Input
            value={uf}
            onChange={(e) => setUf(e.target.value.toUpperCase().slice(0, 2))}
            maxLength={2}
            className="mono"
          />
        </div>
      </div>
      <Button
        onClick={() => {
          if (!nome.trim()) {
            toast.error("Informe ao menos a razão social ou nome.");
            return;
          }
          onSalvar({
            id: `cp-${Date.now()}`,
            tipo,
            documento,
            nome: nome.trim(),
            email: email.trim() || undefined,
            endereco:
              logradouro && municipio && uf
                ? {
                    logradouro,
                    numero,
                    bairro,
                    municipio,
                    uf,
                    cep,
                  }
                : undefined,
          });
        }}
        size="sm"
        className="self-start"
      >
        Salvar e continuar
      </Button>
    </div>
  );
}
