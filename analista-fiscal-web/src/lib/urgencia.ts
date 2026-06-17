/**
 * lib/urgencia.ts
 *
 * Classifica um vencimento em três níveis de urgência e devolve metadados
 * para renderizar via Pill (cor + ícone + palavra).
 *
 * Níveis:
 *  - danger  ≤ 3 dias → vence muito em breve (multa automática 2026)
 *  - ochre   ≤ 7 dias → vence esta semana
 *  - neutro  > 7 dias → prazo confortável
 *
 * Uso:
 *   const urg = classificarUrgencia(evento.data);
 *   <Pill tom={urg.pillTom}>{urg.rotulo}</Pill>
 */

import type { PillTom } from "@/components/shared/pill";

// ─── Tipos ────────────────────────────────────────────────────────────────────

export type NivelUrgencia = "danger" | "ochre" | "neutro";

export interface ResultadoUrgencia {
  /** Nível semântico — use para lógica condicional. */
  nivel: NivelUrgencia;
  /** Rótulo legível — ex.: "Vence hoje", "Vence em 5 dias", "Vence em 20 dias". */
  rotulo: string;
  /** Ícone Unicode para renderizar ao lado do rótulo (acessível via aria-hidden). */
  icone: string;
  /** Tom do Pill correspondente ao nível. */
  pillTom: PillTom;
  /** Número de dias até o vencimento (pode ser negativo se vencido). */
  diasRestantes: number;
}

// ─── Classificador ────────────────────────────────────────────────────────────

/**
 * Classifica o nível de urgência de um vencimento.
 *
 * @param dataVencimento - Data de vencimento em formato ISO "YYYY-MM-DD"
 *   ou objeto `Date`. A comparação é feita em relação a `hoje` (default: agora).
 * @param hoje - Data de referência (default: new Date()).
 */
export function classificarUrgencia(
  dataVencimento: string | Date,
  hoje: Date = new Date()
): ResultadoUrgencia {
  const venc =
    typeof dataVencimento === "string"
      ? new Date(`${dataVencimento}T12:00:00`)
      : dataVencimento;

  // Zeramos a hora da referência para contar dias inteiros
  const hojeNoon = new Date(hoje);
  hojeNoon.setHours(12, 0, 0, 0);

  const diffMs = venc.getTime() - hojeNoon.getTime();
  const dias = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (dias < 0) {
    // Já vencido
    return {
      nivel: "danger",
      rotulo: diasParaRotulo(dias),
      icone: "●",
      pillTom: "error" satisfies PillTom,
      diasRestantes: dias,
    };
  }

  if (dias <= 3) {
    return {
      nivel: "danger",
      rotulo: diasParaRotulo(dias),
      icone: "●",
      pillTom: "error" satisfies PillTom,
      diasRestantes: dias,
    };
  }

  if (dias <= 7) {
    return {
      nivel: "ochre",
      rotulo: diasParaRotulo(dias),
      icone: "◐",
      pillTom: "warn" satisfies PillTom,
      diasRestantes: dias,
    };
  }

  return {
    nivel: "neutro",
    rotulo: diasParaRotulo(dias),
    icone: "○",
    pillTom: "neutral" satisfies PillTom,
    diasRestantes: dias,
  };
}

// ─── Helpers internos ────────────────────────────────────────────────────────

function diasParaRotulo(dias: number): string {
  if (dias < -1) return `Venceu há ${Math.abs(dias)} dias`;
  if (dias === -1) return "Venceu ontem";
  if (dias === 0) return "Vence hoje";
  if (dias === 1) return "Vence amanhã";
  if (dias <= 7) return `Vence em ${dias} dias`;
  return `Vence em ${dias} dias`;
}

/**
 * Retorna `true` se o vencimento for danger (≤ 3 dias ou vencido).
 * Útil para decidir se exibe o card de urgência no topo da home.
 */
export function ehUrgente(dataVencimento: string | Date, hoje: Date = new Date()): boolean {
  return classificarUrgencia(dataVencimento, hoje).nivel === "danger";
}

/**
 * Ordena um array de itens com campo `data` por urgência (mais urgente primeiro).
 */
export function ordenarPorUrgencia<T extends { data: string }>(itens: T[]): T[] {
  return [...itens].sort((a, b) => {
    const dA = classificarUrgencia(a.data).diasRestantes;
    const dB = classificarUrgencia(b.data).diasRestantes;
    return dA - dB;
  });
}
