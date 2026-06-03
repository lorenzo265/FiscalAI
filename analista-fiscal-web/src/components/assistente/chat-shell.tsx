"use client";

import * as React from "react";
import { Loader2, Send, Trash2 } from "lucide-react";
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
        compacto
          ? ""
          : "rounded-[var(--radius-md)] border bg-[var(--color-card)] overflow-hidden"
      )}
      style={!compacto ? { borderColor: "var(--color-rule-2)" } : undefined}
    >
      {/* ── cabeçalho (somente modo não-compacto) ── */}
      {!compacto ? (
        <div
          className="flex items-center justify-between gap-2 px-4 py-3 border-b"
          style={{ borderColor: "var(--color-rule)" }}
        >
          <div className="flex items-center gap-2">
            {/* quadrado técnico Arkan */}
            <div
              className="size-7 rounded-[var(--radius-sm)] grid place-items-center border shrink-0"
              style={{
                background: "var(--color-green-wash)",
                borderColor: "var(--color-green)",
                color: "var(--color-green)",
              }}
            >
              <span className="mono text-[9px] font-bold uppercase leading-none">
                AR
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--color-ink)]">
                Arkan Assistente
              </p>
              <p className="text-[10px] mono uppercase tracking-[0.16em] text-[var(--color-ink-3)]">
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
            className="text-xs text-[var(--color-ink-3)] hover:text-[var(--color-ink)]"
          >
            <Trash2 className="size-3.5" /> Limpar
          </Button>
        </div>
      ) : null}

      {/* ── área de mensagens ── */}
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

      {/* ── sugestões iniciais (só quando histórico está vazio) ── */}
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
              className="text-[10px] mono uppercase tracking-[0.12em] font-bold px-2.5 py-1 rounded-[var(--radius-sm)] border transition-colors hover:bg-[var(--color-paper-2)]"
              style={{
                borderColor: "var(--color-rule-2)",
                color: "var(--color-ink-2)",
              }}
            >
              {s.texto}
            </button>
          ))}
        </div>
      ) : null}

      {/* ── campo de entrada ── */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void enviarMensagem(texto);
        }}
        className="flex items-center gap-2 px-3 py-3 border-t"
        style={{ borderColor: "var(--color-rule)" }}
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
