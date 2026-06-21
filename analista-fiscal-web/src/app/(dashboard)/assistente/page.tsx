import { ChatShell } from "@/components/assistente/chat-shell";

export default function AssistentePage() {
  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-12rem)] min-h-[520px]">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold">
          Assistente
        </span>
        <h1 className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight">
          Analista fiscal — sempre disponível
        </h1>
        <p className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1">
          Tira dúvidas sobre DAS, fluxo de caixa, Fator R e certidões. Todas
          as respostas são baseadas nos dados reais da sua empresa, com citação
          da fonte para auditoria.
        </p>
      </header>

      <div className="flex-1 min-h-0">
        <ChatShell />
      </div>
    </div>
  );
}
