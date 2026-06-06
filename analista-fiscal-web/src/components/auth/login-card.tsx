"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowRight, Mail, Lock, KeyRound, Building2, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Logo } from "@/components/layout/logo";
import { api } from "@/lib/api-client";
import { mensagemAmigavelAuth } from "@/lib/api/auth";
import { setSessao, isLogado } from "@/lib/auth";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const loginSchema = z.object({
  tenantSlug: z
    .string()
    .min(2, "Informe o código da conta")
    .regex(SLUG_RE, "Use apenas letras minúsculas, números e hífens"),
  email: z.string().email("Email inválido"),
  senha: z.string().min(1, "Informe sua senha"),
});
type LoginInput = z.infer<typeof loginSchema>;

const registerSchema = z.object({
  tenantNome: z.string().min(2, "Informe o nome da empresa/conta"),
  tenantSlug: z
    .string()
    .min(2, "Informe um código")
    .regex(SLUG_RE, "Use apenas letras minúsculas, números e hífens"),
  usuarioNome: z.string().min(2, "Informe seu nome"),
  usuarioEmail: z.string().email("Email inválido"),
  usuarioSenha: z.string().min(8, "Mínimo 8 caracteres"),
});
type RegisterInput = z.infer<typeof registerSchema>;

export function LoginCard() {
  const router = useRouter();
  const { empresa, loading, refresh } = useEmpresaAtual();

  React.useEffect(() => {
    if (loading) return;
    if (isLogado()) {
      router.replace(empresa ? "/home" : "/onboarding");
    }
  }, [loading, empresa, router]);

  const loginForm = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
    defaultValues: { tenantSlug: "", email: "", senha: "" },
  });
  const registerForm = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    mode: "onTouched",
    defaultValues: {
      tenantNome: "",
      tenantSlug: "",
      usuarioNome: "",
      usuarioEmail: "",
      usuarioSenha: "",
    },
  });

  const [erro, setErro] = React.useState<string | null>(null);

  async function aposSessao() {
    // Recarrega empresas e decide destino (home se houver empresa, senão onboarding).
    await refresh();
    const id = (await api.empresa.listar().catch(() => []))[0]?.id;
    router.push(id ? "/home" : "/onboarding");
  }

  const onLogin = loginForm.handleSubmit(async (values) => {
    setErro(null);
    try {
      const t = await api.auth.login(values);
      setSessao({
        access_token: t.accessToken,
        expires_in: t.expiresIn,
        email: values.email,
      });
      await aposSessao();
    } catch (err) {
      setErro(mensagemAmigavelAuth(err));
    }
  });

  const onRegister = registerForm.handleSubmit(async (values) => {
    setErro(null);
    try {
      const r = await api.auth.register(values);
      setSessao({
        access_token: r.accessToken,
        expires_in: r.expiresIn,
        email: values.usuarioEmail,
      });
      await aposSessao();
    } catch (err) {
      setErro(mensagemAmigavelAuth(err));
    }
  });

  function preencherDemo() {
    loginForm.setValue("tenantSlug", "demo");
    loginForm.setValue("email", "demo@arkan.dev");
    loginForm.setValue("senha", "arkan1234");
    setErro(null);
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

      <Tabs
        defaultValue="entrar"
        className="w-full"
        onValueChange={() => setErro(null)}
      >
        <TabsList className="grid grid-cols-2 w-full">
          <TabsTrigger value="entrar">Entrar</TabsTrigger>
          <TabsTrigger value="criar">Criar conta</TabsTrigger>
        </TabsList>

        {/* ── Entrar ── */}
        <TabsContent value="entrar" className="mt-5">
          <form onSubmit={onLogin} className="flex flex-col gap-4" noValidate>
            <CampoComIcone
              id="tenant-slug"
              label="Código da conta"
              icon={<KeyRound className="size-4 text-[var(--color-ink-3)]" />}
              placeholder="sua-empresa"
              autoComplete="organization"
              {...loginForm.register("tenantSlug")}
              erro={loginForm.formState.errors.tenantSlug?.message}
            />
            <CampoComIcone
              id="email"
              label="Email"
              type="email"
              icon={<Mail className="size-4 text-[var(--color-ink-3)]" />}
              placeholder="seu@email.com"
              autoComplete="email"
              {...loginForm.register("email")}
              erro={loginForm.formState.errors.email?.message}
            />
            <CampoComIcone
              id="senha"
              label="Senha"
              type="password"
              icon={<Lock className="size-4 text-[var(--color-ink-3)]" />}
              placeholder="sua senha"
              autoComplete="current-password"
              {...loginForm.register("senha")}
              erro={loginForm.formState.errors.senha?.message}
            />

            {erro ? (
              <p className="text-xs text-[var(--color-danger)]">{erro}</p>
            ) : null}

            <Button
              type="submit"
              disabled={loginForm.formState.isSubmitting}
              className="w-full"
            >
              {loginForm.formState.isSubmitting ? "Entrando..." : "Entrar"}
              <ArrowRight className="size-4" />
            </Button>

            <button
              type="button"
              onClick={preencherDemo}
              className="mt-1 mono text-[10px] uppercase tracking-[0.16em] font-bold flex items-center justify-center gap-1.5 text-[var(--color-ink-2)] hover:text-[var(--color-green)] transition-colors"
            >
              <KeyRound className="size-3" />
              Usar demo: demo / demo@arkan.dev
            </button>
          </form>
        </TabsContent>

        {/* ── Criar conta ── */}
        <TabsContent value="criar" className="mt-5">
          <form onSubmit={onRegister} className="flex flex-col gap-4" noValidate>
            <CampoComIcone
              id="tenant-nome"
              label="Nome da conta"
              icon={<Building2 className="size-4 text-[var(--color-ink-3)]" />}
              placeholder="Minha Empresa LTDA"
              {...registerForm.register("tenantNome")}
              erro={registerForm.formState.errors.tenantNome?.message}
            />
            <CampoComIcone
              id="tenant-slug-novo"
              label="Código da conta"
              icon={<KeyRound className="size-4 text-[var(--color-ink-3)]" />}
              placeholder="minha-empresa"
              {...registerForm.register("tenantSlug")}
              erro={registerForm.formState.errors.tenantSlug?.message}
            />
            <CampoComIcone
              id="usuario-nome"
              label="Seu nome"
              icon={<User className="size-4 text-[var(--color-ink-3)]" />}
              placeholder="Seu nome"
              autoComplete="name"
              {...registerForm.register("usuarioNome")}
              erro={registerForm.formState.errors.usuarioNome?.message}
            />
            <CampoComIcone
              id="usuario-email"
              label="Email"
              type="email"
              icon={<Mail className="size-4 text-[var(--color-ink-3)]" />}
              placeholder="seu@email.com"
              autoComplete="email"
              {...registerForm.register("usuarioEmail")}
              erro={registerForm.formState.errors.usuarioEmail?.message}
            />
            <CampoComIcone
              id="usuario-senha"
              label="Senha"
              type="password"
              icon={<Lock className="size-4 text-[var(--color-ink-3)]" />}
              placeholder="mínimo 8 caracteres"
              autoComplete="new-password"
              {...registerForm.register("usuarioSenha")}
              erro={registerForm.formState.errors.usuarioSenha?.message}
            />

            {erro ? (
              <p className="text-xs text-[var(--color-danger)]">{erro}</p>
            ) : null}

            <p className="text-xs text-[var(--color-ink-2)]">
              No próximo passo, você cadastra sua empresa e a Arkan já começa a
              calcular seus impostos.
            </p>
            <Button
              type="submit"
              disabled={registerForm.formState.isSubmitting}
              className="w-full"
            >
              {registerForm.formState.isSubmitting
                ? "Criando..."
                : "Criar conta e começar"}
              <ArrowRight className="size-4" />
            </Button>
          </form>
        </TabsContent>
      </Tabs>

      <p className="mt-6 text-[10px] text-center text-[var(--color-ink-2)] uppercase tracking-[0.16em] mono">
        Conta de demonstração disponível acima
      </p>
    </div>
  );
}

const CampoComIcone = React.forwardRef<
  HTMLInputElement,
  React.ComponentProps<typeof Input> & {
    id: string;
    label: string;
    icon: React.ReactNode;
    erro?: string;
  }
>(function CampoComIcone({ id, label, icon, erro, ...props }, ref) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2">{icon}</span>
        <Input id={id} ref={ref} className="pl-9" {...props} />
      </div>
      {erro ? (
        <p className="text-[11px] text-[var(--color-danger)]">{erro}</p>
      ) : null}
    </div>
  );
});
