"use client";

import * as React from "react";
import { useReducedMotion } from "./use-reduced-motion";

/**
 * useCountUp — anima um número de 0 (ou de um piso) até `value` em ~600ms com
 * ease-out. Identidade Arkan "Claro" v2 (§4 motion): o número-herói "conta" ao
 * aparecer, mas só **1× por valor por sessão** — re-renders com o mesmo valor
 * (ou voltas à mesma tela) mostram o número final, sem re-animar (sem jitter).
 *
 * Regras do contrato:
 *  - honra `prefers-reduced-motion` → troca seca (devolve o valor final na hora);
 *  - tabular-nums fica por conta de quem renderiza (use `.mono`/`.num`);
 *  - só "anima" um número em estado React — nada de width/height/top/left.
 *
 * Uso:
 *   const n = useCountUp(receita);
 *   <span className="mono">{formatarMoeda(n)}</span>
 *
 * `format` opcional permite arredondar/inteirizar os quadros intermediários
 * (ex.: inteiro durante a contagem, decimais no fim).
 */

/** Memória de sessão: valores já animados (não re-animar). */
const animados = new Set<string>();

const DURACAO_MS = 600;

/** ease-out cúbico — desacelera no fim (casa com `--ease-settle`). */
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

interface CountUpOptions {
  /**
   * Chave de identidade do número na tela (ex.: "home:receita"). Se omitida,
   * usa o próprio valor — então o mesmo número não re-anima em lugar nenhum.
   * Informe `id` quando dois lugares mostram o MESMO valor mas devem contar
   * cada um a sua vez.
   */
  id?: string;
  /** Piso de onde a contagem parte (default 0). */
  from?: number;
  /** Duração em ms (default 600). */
  duration?: number;
  /** Transforma cada quadro (ex.: Math.round). Default: identidade. */
  format?: (n: number) => number;
}

export function useCountUp(value: number, options: CountUpOptions = {}): number {
  const { id, from = 0, duration = DURACAO_MS, format } = options;
  const reduced = useReducedMotion();

  const chave = id ?? String(value);
  // Valor inicial SSR-safe e estável: já visto, reduced-motion ou valor não
  // finito → mostra o final imediatamente (sem flash de 0).
  const jaAnimado = animados.has(chave);
  const inicial = reduced || jaAnimado || !Number.isFinite(value) ? value : from;

  const [display, setDisplay] = React.useState<number>(inicial);
  const rafRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (reduced || !Number.isFinite(value)) {
      setDisplay(value);
      return;
    }
    if (animados.has(chave)) {
      setDisplay(value);
      return;
    }
    animados.add(chave);

    const delta = value - from;
    const t0 = performance.now();

    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      const atual = from + delta * easeOutCubic(t);
      setDisplay(format ? format(atual) : atual);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setDisplay(value);
        rafRef.current = null;
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
    // Anima quando o valor-alvo mudar; `chave` deriva de value/id.
  }, [value, from, duration, reduced, chave, format]);

  return display;
}
