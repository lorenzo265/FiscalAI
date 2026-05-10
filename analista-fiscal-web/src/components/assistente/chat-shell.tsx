"use client";

import * as React from "react";
import { Loader2, Send, Sparkles, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { ChatBubble, TypingIndicator } from "@/components/assistente/chat-bubble";
import {
  useEnviarPergunta,
  useLimparHistoricoAssistente,
  useMensagensAssistente,
} from "@/hooks/use-assistente";
import {
  SUGESTOES_INICIAIS,
  type Sugestao,
} from "@/lib/schemas/assistente";
import { cn } from "@/lib/utils";

interface Props {
  compacto?: boolean;
}

export function ChatShell({ compacto }: Props) {
  const { data: mensagens, isLoading, isError, refetch } =
    useMensagensAssistente();
  const enviar = useEnviarPergunta();
  const limpar = useLimparHistoricoAssistente();

  const [texto, setTexto] = React.useState("");
  const fimRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    fimRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens, enviar.isPending]);

  async function enviarMensagem(pergunta: string) {
    const t = pergunta.trim();
    if (!t || enviar.isPending) return;
    setTexto("");
    await enviar.mutateAsync(t);
  }

  function aoEnviarSugestao(s: Sugestao) {
    void enviarMensagem(s.pergunta);
  }

  return (
    <div
      className={cn(
        "flex flex-col h-full min-h-0",
        compacto ? "" : "rounded-lg border bg-[var(--color-card)] overflow-hidden"
      )}
      style={!compacto ? { borderColor: "var(--color-line-2)" } : undefined}
    >
      {!compacto ? (
        <div
          className="flex items-center justify-between gap-2 px-4 py-3 border-b"
          style={{ borderColor: "var(--color-line)" }}
        >
          <div className="flex items-center gap-2">
            <div
              className="size-7 rounded-full grid place-items-center border"
              style={{
                background: "var(--color-lime-d)",
                borderColor: "rgba(163,255,107,0.32)",
                color: "var(--color-lime)",
              }}
            >
              <Sparkles className="size-3.5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--color-txt)]">
                Analista FiscalAI
              </p>
              <p className="text-[10px] mono uppercase tracking-[0.16em] text-[var(--color-txt-3)]">
                Online · responde em tempo real
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            onClick={async () => {
              await limpar.mutateAsync();
            }}
            disabled={limpar.isPending}
            aria-label="Limpar histórico"
            className="text-xs text-[var(--color-txt-3)] hover:text-[var(--color-txt)]"
          >
            <Trash2 className="size-3.5" /> Limpar
          </Button>
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3 min-h-0">
        {isLoading ? (
          <LoadingState titulo="Carregando conversa..." />
        ) : isError ? (
          <ErrorState onTentarNovamente={() => void refetch()} />
        ) : (
          <>
            {(mensagens ?? []).map((m) => (
              <ChatBubble
                key={m.id}
                mensagem={m}
                compacto={compacto}
                onSugestaoClick={(s) => void enviarMensagem(s.pergunta)}
              />
            ))}
            {enviar.isPending ? <TypingIndicator /> : null}
          </>
        )}
        <div ref={fimRef} />
      </div>

      {(mensagens?.length ?? 0) <= 1 && !enviar.isPending ? (
        <div
          className="flex flex-wrap gap-1.5 px-4 pb-3 pt-1"
          aria-label="Sugestões de pergunta"
        >
          {SUGESTOES_INICIAIS.map((s) => (
            <button
              key={s.texto}
              type="button"
              onClick={() => aoEnviarSugestao(s)}
              className="text-[11px] mono uppercase tracking-[0.12em] font-bold px-2.5 py-1 rounded-full border transition-colors hover:bg-[var(--color-card-2)]"
              style={{
                borderColor: "var(--color-line-2)",
                color: "var(--color-txt-2)",
              }}
            >
              {s.texto}
            </button>
          ))}
        </div>
      ) : null}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void enviarMensagem(texto);
        }}
        className="flex items-center gap-2 px-3 py-3 border-t"
        style={{ borderColor: "var(--color-line)" }}
      >
        <Input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Pergunte sobre tributos, fluxo, certidões..."
          autoComplete="off"
          disabled={enviar.isPending}
        />
        <Button
          type="submit"
          disabled={enviar.isPending || !texto.trim()}
          aria-label="Enviar pergunta"
        >
          {enviar.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Send className="size-4" />
          )}
        </Button>
      </form>
    </div>
  );
}
