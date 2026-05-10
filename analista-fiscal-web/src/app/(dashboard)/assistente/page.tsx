import { ChatShell } from "@/components/assistente/chat-shell";

export default function AssistentePage() {
  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-12rem)] min-h-[520px]">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Assistente
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Seu analista fiscal — sempre online
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Tira dúvida sobre DAS, fluxo de caixa, fator R, certidões. Tudo
          baseado nos dados reais da sua empresa, com citação pra você
          conferir o que entrou na resposta.
        </p>
      </header>

      <div className="flex-1 min-h-0">
        <ChatShell />
      </div>
    </div>
  );
}
