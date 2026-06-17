"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { useAgenda } from "@/hooks/use-agenda";
import { classificarUrgencia } from "@/lib/urgencia";
import { traduzirObrigacao } from "@/lib/traducao/obrigacoes";
import type { EventoAgenda } from "@/lib/schemas/agenda";

/**
 * Card fixo no topo da home quando há vencimento ≤ 3 dias.
 * Só renderiza se houver evento danger; invisível caso contrário.
 *
 * Invariante: uma ação por alerta (§7).
 */
export function UrgenciaCard() {
  const { data: eventos } = useAgenda();

  if (!eventos) return null;

  const hoje = new Date();
  // Filtra eventos danger (≤3 dias, não pagos) e pega o mais próximo
  const urgentes = eventos
    .filter((e) => e.status !== "pago" && classificarUrgencia(e.data, hoje).nivel === "danger")
    .sort((a, b) => a.data.localeCompare(b.data));

  const primeiro = urgentes[0];
  if (!primeiro) return null;

  const urg = classificarUrgencia(primeiro.data, hoje);

  return (
    <div
      className="relative rounded-[var(--radius-md)] border p-5 flex items-start gap-3"
      style={{
        borderColor: "var(--color-danger)",
        background: "var(--color-danger-wash)",
      }}
    >
      <AlertTriangle
        className="size-4 mt-0.5 shrink-0"
        style={{ color: "var(--color-danger)" }}
        aria-hidden
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Pill tom="error">{urg.rotulo}</Pill>
          {urgentes.length > 1 ? (
            <span className="mono text-[10px] text-[var(--color-ink-2)] uppercase tracking-[0.1em]">
              +{urgentes.length - 1} {urgentes.length - 1 === 1 ? "outra obrigação" : "outras obrigações"}
            </span>
          ) : null}
        </div>
        <p className="text-sm font-semibold text-[var(--color-ink)] mt-1">
          {resolverTituloPT(primeiro)} vence{" "}
          <span style={{ color: "var(--color-danger)" }}>
            {urg.diasRestantes === 0
              ? "hoje"
              : urg.diasRestantes === 1
                ? "amanhã"
                : urg.diasRestantes < 0
                  ? `há ${Math.abs(urg.diasRestantes)} dias`
                  : `em ${urg.diasRestantes} dias`}
          </span>
          {primeiro.valor ? (
            <>
              {" · "}
              <span className="mono font-bold">
                <Moeda valor={primeiro.valor} />
              </span>
            </>
          ) : null}
        </p>
        <p className="text-xs text-[var(--color-ink-2)] mt-0.5">
          Com a multa automática em vigor desde 2026, atraso gera cobrança no dia seguinte.
        </p>
      </div>
      {/* uma ação única */}
      {primeiro.rota ? (
        <Link
          href={primeiro.rota}
          className="inline-flex items-center gap-1 text-[11px] mono font-bold uppercase tracking-[0.12em] text-[var(--color-danger)] hover:underline shrink-0 mt-0.5"
          aria-label={`Resolver ${resolverTituloPT(primeiro)}`}
        >
          Resolver <ArrowRight className="size-3" aria-hidden />
        </Link>
      ) : (
        <Link
          href="/agenda"
          className="inline-flex items-center gap-1 text-[11px] mono font-bold uppercase tracking-[0.12em] text-[var(--color-danger)] hover:underline shrink-0 mt-0.5"
        >
          Ver agenda <ArrowRight className="size-3" aria-hidden />
        </Link>
      )}
    </div>
  );
}

// ─── helper interno ───────────────────────────────────────────────────────────

function resolverTituloPT(evento: EventoAgenda): string {
  const candidatos = [
    "PGDAS-D", "PGDAS_D", "DCTFWeb", "DCTF", "eSocial", "ESOCIAL",
    "DEFIS", "DAS", "FGTS", "INSS", "GFIP", "DASN-SIMEI", "REINF",
  ];
  for (const token of candidatos) {
    if (evento.titulo.toUpperCase().includes(token.toUpperCase())) {
      const entrada = traduzirObrigacao(token);
      if (entrada) return entrada.titulo;
    }
  }
  return evento.titulo;
}
