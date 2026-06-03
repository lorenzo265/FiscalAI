"use client";

import * as React from "react";

/**
 * Lê `prefers-reduced-motion` de forma reativa e SSR-safe.
 * Retorna `true` quando o usuário pediu menos movimento — todo motion do
 * design-system Arkan deve cair para um fallback estático nesse caso.
 *
 * (Wrapper próprio em vez do hook do Framer para não acoplar callers ao
 * `framer-motion` e para garantir o mesmo valor inicial no SSR: `false`,
 * i.e. assume movimento, e corrige no cliente.)
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    // Safari < 14 usa addListener
    if (mq.addEventListener) mq.addEventListener("change", update);
    else mq.addListener(update);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener("change", update);
      else mq.removeListener(update);
    };
  }, []);

  return reduced;
}
