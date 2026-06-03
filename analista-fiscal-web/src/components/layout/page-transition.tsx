"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import type { ReactNode } from "react";
import { perfRecord } from "@/lib/perf";
import { EASE, useReducedMotion } from "@/lib/motion";

/**
 * PageTransition — entrada/saída coreografada entre rotas (Arkan shell).
 *
 * Coreografia (só transform/opacity/clip-path — perf-safe):
 *  - entrada: clip-path wipe leve de cima + sobe 10px + un-fade (ease-reveal);
 *  - saída: recua 6px + esmaece (ease-settle), rápido para não atrasar a navegação.
 * Sob `prefers-reduced-motion`: troca seca (sem transform/clip), conteúdo sempre
 * visível. Orçamento: 1 entrada por tela (o "signature" fica para cada tela).
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const reduced = useReducedMotion();
  const startRef = React.useRef<number>(
    typeof performance !== "undefined" ? performance.now() : 0
  );

  React.useEffect(() => {
    startRef.current = performance.now();
  }, [pathname]);

  const onEnterComplete = React.useCallback(() => {
    perfRecord("page-transition:enter-complete", startRef.current, { pathname });
  }, [pathname]);

  if (reduced) {
    // Sem movimento: apenas remonta o conteúdo por rota.
    return (
      <div key={pathname} onAnimationEnd={onEnterComplete}>
        {children}
      </div>
    );
  }

  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.div
        key={pathname}
        initial={{ opacity: 0, y: 10, clipPath: "inset(0 0 8% 0)" }}
        animate={{
          opacity: 1,
          y: 0,
          clipPath: "inset(0 0 0% 0)",
          transition: { duration: 0.42, ease: EASE.reveal },
        }}
        exit={{
          opacity: 0,
          y: -6,
          transition: { duration: 0.16, ease: EASE.settle },
        }}
        onAnimationComplete={(def) => {
          if (typeof def === "object" && def && "opacity" in def) {
            onEnterComplete();
          }
        }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
