"use client";

import * as React from "react";
import { useReducedMotion } from "./use-reduced-motion";

/**
 * LenisProvider — scroll suave "premium" do Arkan (a base sensorial das refs
 * fluid.glass / floema). Contrato: `lerp 0.09`, só transform de scroll, fallback
 * total em `prefers-reduced-motion` (devolve scroll nativo).
 *
 * IMPORTANTE (Fase 1): este componente é DONO do design-system mas **NÃO** é
 * plugado no `(dashboard)/layout` aqui — isso é tarefa da Fase 2 (shell). Ele
 * existe pronto para ser consumido.
 *
 * Implementação: smooth-scroll auto-contido por `requestAnimationFrame` + lerp,
 * sem dependência externa, para não quebrar o build (o pacote `lenis` não está
 * instalado). Quando o shell adotar, pode-se trocar por `lenis` mantendo a mesma
 * API de provider — daí o nome. Progressive enhancement: se algo falhar, o
 * scroll nativo continua funcionando.
 */

const LERP = 0.09;

interface LenisProviderProps {
  children: React.ReactNode;
  /** Desliga o smooth scroll (ex.: enquanto um modal trava o body). */
  disabled?: boolean;
}

export function LenisProvider({ children, disabled = false }: LenisProviderProps) {
  const reduced = useReducedMotion();

  React.useEffect(() => {
    if (disabled || reduced) return;
    if (typeof window === "undefined") return;
    // Só desktop com ponteiro fino: em touch o scroll nativo já é ótimo e o
    // smooth-scroll por JS atrapalha o "fling" do dedo.
    const fine = window.matchMedia("(pointer: fine)").matches;
    if (!fine) return;

    let target = window.scrollY;
    let current = window.scrollY;
    let raf = 0;
    let running = false;

    const root = document.documentElement;

    const clamp = (v: number) =>
      Math.max(0, Math.min(v, root.scrollHeight - window.innerHeight));

    const tick = () => {
      current += (target - current) * LERP;
      if (Math.abs(target - current) < 0.15) {
        current = target;
        running = false;
        window.scrollTo(0, Math.round(current));
        return;
      }
      window.scrollTo(0, Math.round(current));
      raf = requestAnimationFrame(tick);
    };

    const start = () => {
      if (running) return;
      running = true;
      raf = requestAnimationFrame(tick);
    };

    const onWheel = (e: WheelEvent) => {
      // Respeita zoom (ctrl) e gestos horizontais.
      if (e.ctrlKey) return;
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      e.preventDefault();
      target = clamp(target + e.deltaY);
      start();
    };

    // Se o usuário rolar por teclado/scrollbar/âncora, ressincroniza o alvo.
    const onScrollSync = () => {
      if (!running) {
        target = window.scrollY;
        current = window.scrollY;
      }
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("scroll", onScrollSync, { passive: true });

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("scroll", onScrollSync);
    };
  }, [disabled, reduced]);

  return <>{children}</>;
}
