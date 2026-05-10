"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Info,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  TIPO_CITACAO_LABEL,
  type Bloco,
  type Citacao,
  type MensagemAssistente,
  type Sugestao,
} from "@/lib/schemas/assistente";

interface Props {
  mensagem: MensagemAssistente;
  onSugestaoClick?: (sugestao: Sugestao) => void;
  compacto?: boolean;
}

export function ChatBubble({ mensagem, onSugestaoClick, compacto }: Props) {
  if (mensagem.role === "user") return <BubbleUsuario mensagem={mensagem} />;
  return (
    <BubbleAssistente
      mensagem={mensagem}
      onSugestaoClick={onSugestaoClick}
      compacto={compacto}
    />
  );
}

function BubbleUsuario({ mensagem }: { mensagem: MensagemAssistente }) {
  return (
    <div className="flex justify-end">
      <div
        className="max-w-[78%] rounded-md px-3 py-2 text-sm leading-relaxed"
        style={{
          background: "var(--color-card-2)",
          color: "var(--color-txt)",
          border: "1px solid var(--color-line-2)",
        }}
      >
        {mensagem.texto}
      </div>
    </div>
  );
}

function BubbleAssistente({
  mensagem,
  onSugestaoClick,
  compacto,
}: {
  mensagem: MensagemAssistente;
  onSugestaoClick?: (s: Sugestao) => void;
  compacto?: boolean;
}) {
  return (
    <div className="flex items-start gap-2">
      <div
        className="size-7 rounded-full grid place-items-center shrink-0 border"
        style={{
          background: "var(--color-lime-d)",
          borderColor: "rgba(163,255,107,0.32)",
          color: "var(--color-lime)",
        }}
        aria-hidden
      >
        <Sparkles className="size-3.5" />
      </div>
      <div
        className={cn(
          "rounded-md px-3.5 py-3 flex flex-col gap-2.5",
          compacto ? "max-w-full" : "max-w-[78%]"
        )}
        style={{
          background: "var(--color-card)",
          color: "var(--color-txt)",
          border: "1px solid var(--color-line)",
          borderLeft: "2px solid var(--color-lime)",
        }}
      >
        <p className="text-sm leading-relaxed whitespace-pre-line">
          {renderTextoFormatado(mensagem.texto)}
        </p>

        {mensagem.blocos.map((bloco, i) => (
          <BlocoView key={i} bloco={bloco} />
        ))}

        {mensagem.citacoes.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {mensagem.citacoes.map((c, i) => (
              <CitacaoChip key={i} citacao={c} />
            ))}
          </div>
        ) : null}

        {mensagem.sugestoes.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {mensagem.sugestoes.map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onSugestaoClick?.(s)}
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
      </div>
    </div>
  );
}

function BlocoView({ bloco }: { bloco: Bloco }) {
  if (bloco.tipo === "texto") {
    return <p className="text-sm text-[var(--color-txt-2)]">{bloco.texto}</p>;
  }
  if (bloco.tipo === "stat") {
    const corValor =
      bloco.tom === "ok"
        ? "var(--color-lime)"
        : bloco.tom === "warn"
          ? "var(--color-amber)"
          : bloco.tom === "error"
            ? "var(--color-red)"
            : bloco.tom === "info"
              ? "var(--color-blue)"
              : "var(--color-txt)";
    return (
      <div
        className="rounded-md border p-3 flex items-center justify-between gap-3"
        style={{
          background: "var(--color-card-2)",
          borderColor: "var(--color-line-2)",
        }}
      >
        <span className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--color-txt-3)]">
          {bloco.rotulo}
        </span>
        <span
          className="mono text-base font-bold"
          style={{ color: corValor }}
        >
          {bloco.valor}
        </span>
      </div>
    );
  }
  if (bloco.tipo === "lista") {
    return (
      <div
        className="rounded-md border"
        style={{
          background: "var(--color-card-2)",
          borderColor: "var(--color-line-2)",
        }}
      >
        {bloco.titulo ? (
          <div
            className="px-3 py-1.5 border-b text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-txt-3)]"
            style={{ borderColor: "var(--color-line)" }}
          >
            {bloco.titulo}
          </div>
        ) : null}
        <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
          {bloco.itens.map((item, i) => (
            <li
              key={i}
              className="px-3 py-1.5 flex items-center justify-between gap-3 text-xs"
            >
              <span className="text-[var(--color-txt)]">{item.rotulo}</span>
              {item.valor ? (
                <span className="mono text-[var(--color-txt-2)] shrink-0">
                  {item.valor}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (bloco.tipo === "alerta") {
    const Icon =
      bloco.tom === "ok"
        ? CheckCircle2
        : bloco.tom === "warn" || bloco.tom === "error"
          ? AlertTriangle
          : Info;
    const cor =
      bloco.tom === "ok"
        ? "var(--color-lime)"
        : bloco.tom === "warn"
          ? "var(--color-amber)"
          : bloco.tom === "error"
            ? "var(--color-red)"
            : "var(--color-blue)";
    const corBg =
      bloco.tom === "ok"
        ? "var(--color-lime-d)"
        : bloco.tom === "warn"
          ? "var(--color-amber-d)"
          : bloco.tom === "error"
            ? "var(--color-red-d)"
            : "var(--color-blue-d)";
    return (
      <div
        className="rounded-md border p-2.5 flex items-start gap-2"
        style={{ background: corBg, borderColor: "transparent" }}
      >
        <Icon className="size-3.5 mt-0.5 shrink-0" style={{ color: cor }} />
        <div className="flex flex-col gap-0.5 min-w-0">
          <p className="text-xs font-semibold" style={{ color: cor }}>
            {bloco.titulo}
          </p>
          {bloco.descricao ? (
            <p className="text-[11px] text-[var(--color-txt-2)]">
              {bloco.descricao}
            </p>
          ) : null}
        </div>
      </div>
    );
  }
  return null;
}

function CitacaoChip({ citacao }: { citacao: Citacao }) {
  const conteudo = (
    <span
      className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] mono border transition-colors"
      style={{
        background: "var(--color-card-2)",
        borderColor: "var(--color-line-2)",
        color: "var(--color-txt-2)",
      }}
    >
      <FileText className="size-3" />
      <span className="text-[var(--color-txt-3)]">
        {TIPO_CITACAO_LABEL[citacao.tipo]} ·
      </span>
      <span className="text-[var(--color-txt)]">{citacao.rotulo}</span>
    </span>
  );
  if (citacao.rota) {
    return (
      <Link
        href={citacao.rota}
        className="hover:[&>span]:bg-[var(--color-card-3)]"
      >
        {conteudo}
      </Link>
    );
  }
  return conteudo;
}

function renderTextoFormatado(texto: string): React.ReactNode {
  // Suporte a **negrito**
  const partes = texto.split(/(\*\*[^*]+\*\*)/g);
  return partes.map((parte, i) => {
    if (parte.startsWith("**") && parte.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-[var(--color-txt)]">
          {parte.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={i}>{parte}</React.Fragment>;
  });
}

export function TypingIndicator() {
  return (
    <div className="flex items-start gap-2">
      <div
        className="size-7 rounded-full grid place-items-center shrink-0 border"
        style={{
          background: "var(--color-lime-d)",
          borderColor: "rgba(163,255,107,0.32)",
          color: "var(--color-lime)",
        }}
        aria-hidden
      >
        <Sparkles className="size-3.5" />
      </div>
      <div
        className="rounded-md px-3.5 py-3 flex items-center gap-1.5 border"
        style={{
          background: "var(--color-card)",
          borderColor: "var(--color-line)",
          borderLeft: "2px solid var(--color-lime)",
        }}
        aria-label="Assistente digitando"
      >
        <Ponto delay={0} />
        <Ponto delay={150} />
        <Ponto delay={300} />
      </div>
    </div>
  );
}

function Ponto({ delay }: { delay: number }) {
  return (
    <span
      className="size-1.5 rounded-full animate-pulse"
      style={{
        background: "var(--color-lime)",
        animationDelay: `${delay}ms`,
        animationDuration: "1.2s",
      }}
    />
  );
}

