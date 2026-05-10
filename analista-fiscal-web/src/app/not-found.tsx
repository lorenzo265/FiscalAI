import Link from "next/link";
import { ArrowLeft, Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/layout/logo";

export default function NotFoundPage() {
  return (
    <main
      className="min-h-screen grid place-items-center px-6 py-12"
      style={{ background: "var(--color-bg)" }}
    >
      <div className="flex flex-col items-center text-center max-w-md gap-6">
        <div className="flex items-center gap-2.5">
          <Logo size={32} />
          <div className="flex flex-col leading-none text-left">
            <span className="text-base font-bold tracking-tight text-[var(--color-txt)]">
              FiscalAI
            </span>
            <span className="mono text-[9px] uppercase tracking-[0.18em] text-[var(--color-txt-3)] mt-0.5">
              v0.1
            </span>
          </div>
        </div>

        <div
          className="size-20 rounded-full grid place-items-center border"
          style={{
            background: "var(--color-card-2)",
            borderColor: "var(--color-line-2)",
          }}
        >
          <Compass className="size-9 text-[var(--color-lime)]" />
        </div>

        <div className="flex flex-col gap-2">
          <span className="mono text-[10px] uppercase tracking-[0.2em] font-bold text-[var(--color-txt-3)]">
            erro 404 · página não encontrada
          </span>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[var(--color-txt)]">
            Esse caminho não existe
          </h1>
          <p className="text-sm text-[var(--color-txt-2)] leading-relaxed max-w-sm mx-auto">
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
