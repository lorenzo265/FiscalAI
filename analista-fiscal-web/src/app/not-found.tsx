import Link from "next/link";
import { ArrowLeft, Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/layout/logo";

export default function NotFoundPage() {
  return (
    <main
      className="min-h-screen grid place-items-center px-6 py-12"
      style={{ background: "var(--color-paper)" }}
    >
      <div className="flex flex-col items-center text-center max-w-md gap-6">
        <div className="flex items-center gap-2.5">
          <Logo size={32} />
          <div className="flex flex-col leading-none text-left">
            <span className="font-serif text-base font-semibold tracking-tight text-[var(--color-ink)]">
              Arkan
            </span>
            <span className="mono text-[9px] uppercase tracking-[0.18em] text-[var(--color-ink-2)] mt-0.5">
              v0.1
            </span>
          </div>
        </div>

        <div
          className="size-20 rounded-[var(--radius-md)] grid place-items-center border"
          style={{
            background: "var(--color-card)",
            borderColor: "var(--color-rule-2)",
          }}
        >
          <Compass className="size-9 text-[var(--color-green)]" />
        </div>

        <div className="flex flex-col gap-2">
          <span className="mono text-[10px] uppercase tracking-[0.2em] font-bold text-[var(--color-ink-2)]">
            erro 404 · página não encontrada
          </span>
          <h1 className="font-serif text-3xl md:text-4xl font-semibold tracking-tight text-[var(--color-ink)]">
            Esse caminho não existe
          </h1>
          <p className="text-sm text-[var(--color-ink-2)] leading-relaxed max-w-sm mx-auto">
            Pode ser que a página tenha sido movida ou que o link esteja com um
            erro de digitação. Vamos te levar de volta ao painel.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button asChild>
            <Link href="/home">
              <ArrowLeft className="size-4" />
              Voltar para o painel
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/configuracoes">Ir para configurações</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
