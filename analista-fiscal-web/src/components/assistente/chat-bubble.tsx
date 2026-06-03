"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Info,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  TIPO_CITACAO_LABEL,
  type Bloco,
  type Citacao,
  type MensagemAssistente,
  type Sugestao,
} from "@/lib/schemas/assistente";

/* ── ícone Arkan do assistente (quadrado técnico, não bolinha neon) ── */
function AssistenteIcone({ small }: { small?: boolean }) {
  const s = small ? "size-6" : "size-7";
  return (
    <div
      className={cn(
        s,
        "rounded-[var(--radius-sm)] grid place-items-center shrink-0 border"
      )}
      style={{
        background: "var(--color-green-wash)",
        borderColor: "var(--color-green)",
        color: "var(--color-green)",
      }}
      aria-hidden
    >
      {/* "A" minimalista em mono — marca do Arkan Assistente */}
      <span
        className="mono text-[10px] font-bold uppercase leading-none"
        style={{ letterSpacing: "0.04em" }}
      >
        AR
      </span>
    </div>
  );
}

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
        className="max-w-[78%] rounded-[var(--radius-md)] px-3 py-2 text-sm leading-relaxed"
        style={{
          background: "var(--color-paper-2)",
          color: "var(--color-ink)",
          border: "1px solid var(--color-rule-2)",
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
      <AssistenteIcone />
      <div
        className={cn(
          "rounded-[var(--radius-md)] px-3.5 py-3 flex flex-col gap-2.5",
          compacto ? "max-w-full" : "max-w-[78%]"
        )}
        style={{
          background: "var(--color-card)",
          color: "var(--color-ink)",
          border: "1px solid var(--color-rule)",
          borderLeft: "2px solid var(--color-green)",
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
      </div>
    </div>
  );
}

function BlocoView({ bloco }: { bloco: Bloco }) {
  if (bloco.tipo === "texto") {
    return <p className="text-sm text-[var(--color-ink-2)]">{bloco.texto}</p>;
  }
  if (bloco.tipo === "stat") {
    const corValor =
      bloco.tom === "ok"
        ? "var(--color-green)"
        : bloco.tom === "warn"
          ? "var(--color-ochre)"
          : bloco.tom === "error"
            ? "var(--color-danger)"
            : "var(--color-ink)";
    return (
      <div
        className="rounded-[var(--radius-md)] border p-3 flex items-center justify-between gap-3"
        style={{
          background: "var(--color-paper-2)",
          borderColor: "var(--color-rule-2)",
        }}
      >
        <span className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-ink-3)] mono">
          {bloco.rotulo}
        </span>
        <span
          className="mono text-base font-bold"
          style={{ color: corValor, fontVariantNumeric: "tabular-nums" }}
        >
          {bloco.valor}
        </span>
      </div>
    );
  }
  if (bloco.tipo === "lista") {
    return (
      <div
        className="rounded-[var(--radius-md)] border overflow-hidden"
        style={{
          background: "var(--color-paper-2)",
          borderColor: "var(--color-rule-2)",
        }}
      >
        {bloco.titulo ? (
          <div
            className="px-3 py-1.5 border-b text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-ink-3)]"
            style={{ borderColor: "var(--color-rule)" }}
          >
            {bloco.titulo}
          </div>
        ) : null}
        <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
          {bloco.itens.map((item, i) => (
            <li
              key={i}
              className="px-3 py-1.5 flex items-center justify-between gap-3 text-xs"
            >
              <span className="text-[var(--color-ink)]">{item.rotulo}</span>
              {item.valor ? (
                <span
                  className="mono text-[var(--color-ink-2)] shrink-0"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
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
        ? "var(--color-green)"
        : bloco.tom === "warn"
          ? "var(--color-ochre)"
          : bloco.tom === "error"
            ? "var(--color-danger)"
            : "var(--color-ink-2)";
    return (
      <div
        className="rounded-[var(--radius-md)] border p-2.5 flex items-start gap-2"
        style={{
          background: "var(--color-paper-2)",
          borderColor: "var(--color-rule)",
          borderLeft: `2px solid ${cor}`,
        }}
      >
        <Icon className="size-3.5 mt-0.5 shrink-0" style={{ color: cor }} />
        <div className="flex flex-col gap-0.5 min-w-0">
          <p className="text-xs font-semibold" style={{ color: cor }}>
            {bloco.titulo}
          </p>
          {bloco.descricao ? (
            <p className="text-[11px] text-[var(--color-ink-2)]">
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
      className="inline-flex items-center gap-1 px-2 py-1 rounded-[var(--radius-sm)] text-[10px] mono border transition-colors"
      style={{
        background: "var(--color-paper-2)",
        borderColor: "var(--color-rule-2)",
        color: "var(--color-ink-2)",
      }}
    >
      <FileText className="size-3 shrink-0" />
      <span className="text-[var(--color-ink-3)]">
        {TIPO_CITACAO_LABEL[citacao.tipo]} ·
      </span>
      <span className="text-[var(--color-ink)]">{citacao.rotulo}</span>
    </span>
  );
  if (citacao.rota) {
    return (
      <Link
        href={citacao.rota}
        className="hover:[&>span]:bg-[var(--color-rule)]"
      >
        {conteudo}
      </Link>
    );
  }
  return conteudo;
}

function renderTextoFormatado(texto: string): React.ReactNode {
  const partes = texto.split(/(\*\*[^*]+\*\*)/g);
  return partes.map((parte, i) => {
    if (parte.startsWith("**") && parte.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-[var(--color-ink)]">
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
      <AssistenteIcone />
      <div
        className="rounded-[var(--radius-md)] px-3.5 py-3 flex items-center gap-1.5 border"
        style={{
          background: "var(--color-card)",
          borderColor: "var(--color-rule)",
          borderLeft: "2px solid var(--color-green)",
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
        background: "var(--color-green)",
        animationDelay: `${delay}ms`,
        animationDuration: "1.2s",
      }}
    />
  );
}
