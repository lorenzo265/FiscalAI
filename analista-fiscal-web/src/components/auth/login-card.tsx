"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Mail, Lock, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Logo } from "@/components/layout/logo";
import { entrar, isLogado } from "@/lib/auth";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function LoginCard() {
  const router = useRouter();
  const { empresa, loading } = useEmpresaAtual();
  const [email, setEmail] = React.useState("");
  const [senha, setSenha] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [erro, setErro] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (loading) return;
    if (isLogado()) {
      router.replace(empresa ? "/home" : "/onboarding");
    }
  }, [loading, empresa, router]);

  async function handleEntrar(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !senha) {
      setErro("Preencha email e senha.");
      return;
    }
    setErro(null);
    setSubmitting(true);
    await new Promise((r) => setTimeout(r, 700));
    entrar(email);
    router.push(empresa ? "/home" : "/onboarding");
  }

  function preencherDemo() {
    setEmail("demo@arkan.com");
    setSenha("demo123");
  }

  return (
    <div
      className="w-full max-w-[420px] rounded-[var(--radius-md)] border p-8 shadow-[0_24px_60px_-30px_rgba(27,26,21,0.45)]"
      style={{
        background: "var(--color-card)",
        borderColor: "var(--color-rule-2)",
      }}
    >
      <div className="flex flex-col items-center gap-3 mb-6">
        <Logo size={56} />
        <div className="text-center">
          <h1 className="font-serif text-xl font-semibold tracking-tight text-[var(--color-ink)]">
            Arkan
          </h1>
          <p className="text-xs text-[var(--color-ink-2)] mt-1">
            Você sabe o que está acontecendo no seu fiscal — sem precisar ser contador.
          </p>
        </div>
      </div>

      <Tabs defaultValue="entrar" className="w-full">
        <TabsList className="grid grid-cols-2 w-full">
          <TabsTrigger value="entrar">Entrar</TabsTrigger>
          <TabsTrigger value="criar">Criar conta</TabsTrigger>
        </TabsList>

        <TabsContent value="entrar" className="mt-5">
          <form onSubmit={handleEntrar} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--color-ink-3)]" />
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="seu@email.com"
                  className="pl-9"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="senha">Senha</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--color-ink-3)]" />
                <Input
                  id="senha"
                  type="password"
                  autoComplete="current-password"
                  placeholder="sua senha"
                  className="pl-9"
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                />
              </div>
            </div>

            {erro ? (
              <p className="text-xs text-[var(--color-danger)]">{erro}</p>
            ) : null}

            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Entrando..." : "Entrar"}
              <ArrowRight className="size-4" />
            </Button>

            <button
              type="button"
              onClick={preencherDemo}
              className="mt-1 mono text-[10px] uppercase tracking-[0.16em] font-bold flex items-center justify-center gap-1.5 text-[var(--color-ink-2)] hover:text-[var(--color-green)] transition-colors"
            >
              <KeyRound className="size-3" />
              Usar demo: demo@arkan.com / demo123
            </button>
          </form>
        </TabsContent>

        <TabsContent value="criar" className="mt-5">
          <form onSubmit={handleEntrar} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email-novo">Email</Label>
              <Input
                id="email-novo"
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="senha-nova">Senha</Label>
              <Input
                id="senha-nova"
                type="password"
                placeholder="crie uma senha"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
              />
            </div>
            <p className="text-xs text-[var(--color-ink-2)]">
              No próximo passo, você cadastra sua empresa e a Arkan já começa a
              calcular seus impostos.
            </p>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Criando..." : "Criar conta e começar"}
              <ArrowRight className="size-4" />
            </Button>
          </form>
        </TabsContent>
      </Tabs>

      <p className="mt-6 text-[10px] text-center text-[var(--color-ink-2)] uppercase tracking-[0.16em] mono">
        Demonstração — todos os dados são simulados
      </p>
    </div>
  );
}
