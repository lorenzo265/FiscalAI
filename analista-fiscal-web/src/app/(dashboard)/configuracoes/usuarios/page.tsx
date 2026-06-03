"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, Mail, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Pill } from "@/components/shared/pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { ConfiguracoesSubnav } from "@/components/configuracoes/configuracoes-subnav";
import { emailLogado } from "@/lib/auth";

export default function ConfiguracoesUsuariosPage() {
  const [email, setEmail] = React.useState<string | null>(null);
  const [convidando, setConvidando] = React.useState(false);
  const [novoEmail, setNovoEmail] = React.useState("");
  const [enviando, setEnviando] = React.useState(false);

  React.useEffect(() => {
    setEmail(emailLogado());
  }, []);

  const inicial = (email ?? "?").trim().charAt(0).toUpperCase();

  function enviarConvite(e: React.FormEvent) {
    e.preventDefault();
    if (!novoEmail.includes("@")) {
      toast.error("Informe um e-mail válido.");
      return;
    }
    setEnviando(true);
    setTimeout(() => {
      toast.success("Convite enviado", {
        description: `Avisamos ${novoEmail} para entrar no painel.`,
      });
      setEnviando(false);
      setConvidando(false);
      setNovoEmail("");
    }, 700);
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Link
          href="/configuracoes"
          className="text-[11px] mono uppercase tracking-[0.12em] text-[var(--color-ink-3)] font-bold inline-flex items-center gap-1 hover:text-[var(--color-ink-2)] transition-colors"
        >
          <ArrowLeft className="size-3" />
          Configurações
        </Link>
        <h1 className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight mt-1">
          Usuários e acessos
        </h1>
        <p className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1">
          Convide seu contador, sócio ou time financeiro. Cada pessoa entra com
          e-mail próprio e tem trilha de auditoria separada.
        </p>
      </header>

      <ConfiguracoesSubnav />

      {/* Fig. 01 — usuários ativos */}
      <Framed marks={false} tone="rule" surface="card" padded={false}>
        <div className="px-5 pt-4 pb-2 flex items-center justify-between gap-2">
          <Fig n={1} titulo="Usuários com acesso" size="sm" />
          <Button onClick={() => setConvidando(true)} size="sm">
            <UserPlus className="size-4" />
            Convidar
          </Button>
        </div>
        <Ruler />
        <ul>
          <li className="flex items-center gap-4 px-5 py-4">
            {/* avatar em quadrado técnico */}
            <div
              className="size-10 rounded-[var(--radius-sm)] grid place-items-center font-bold mono text-sm shrink-0 border"
              style={{
                background: "var(--color-green-wash)",
                color: "var(--color-green)",
                borderColor: "var(--color-green)",
              }}
            >
              {inicial}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-[var(--color-ink)] truncate">
                  {email ?? "Você"}
                </span>
                <Pill tom="ok">
                  <span className="flex items-center gap-1">você</span>
                </Pill>
              </div>
              <p className="text-xs text-[var(--color-ink-3)] mono mt-0.5">
                Administrador · acesso total
              </p>
            </div>
            <span className="text-[11px] text-[var(--color-ink-3)] mono hidden md:block"
                  style={{ fontVariantNumeric: "tabular-nums" }}>
              Último acesso: agora
            </span>
          </li>
        </ul>
      </Framed>

      {/* nota sobre link mágico */}
      <Framed marks={false} tone="rule" surface="paper-2" className="flex items-start gap-3">
        <Mail className="size-4 text-[var(--color-ink-2)] mt-0.5 shrink-0" />
        <p className="text-sm text-[var(--color-ink-2)] leading-relaxed">
          Os convidados recebem por e-mail um link de acesso seguro. Você pode
          revogar o acesso a qualquer momento sem trocar senhas.
        </p>
      </Framed>

      {/* modal de convite */}
      <Dialog open={convidando} onOpenChange={setConvidando}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-serif">Convidar novo usuário</DialogTitle>
            <DialogDescription>
              Informe o e-mail. O convidado entra como contador — acesso de
              leitura e lançamentos.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={enviarConvite} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label
                htmlFor="email-convidado"
                className="text-[11px] mono uppercase tracking-[0.12em] font-bold text-[var(--color-ink-3)]"
              >
                E-mail do convidado
              </Label>
              <Input
                id="email-convidado"
                type="email"
                placeholder="contador@escritorio.com.br"
                value={novoEmail}
                onChange={(e) => setNovoEmail(e.target.value)}
                autoFocus
              />
            </div>

            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setConvidando(false)}
                disabled={enviando}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={enviando || !novoEmail.trim()}>
                {enviando ? "Enviando..." : "Enviar convite"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
