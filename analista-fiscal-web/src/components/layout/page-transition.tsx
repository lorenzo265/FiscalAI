"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import type { ReactNode } from "react";
import { perfRecord } from "@/lib/perf";

export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const startRef = React.useRef<number>(
    typeof performance !== "undefined" ? performance.now() : 0
  );

  React.useEffect(() => {
    startRef.current = performance.now();
  }, [pathname]);

  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.div
        key={pathname}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -2 }}
        transition={{ duration: 0.12, ease: [0.22, 0.61, 0.36, 1] }}
        onAnimationComplete={(def) => {
          if (
            def === "animate" ||
            (typeof def === "object" && def && "opacity" in def)
          ) {
            perfRecord("page-transition:enter-complete", startRef.current, {
              pathname,
            });
          }
        }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
