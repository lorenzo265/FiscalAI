"use client";

import * as React from "react";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { QueryProvider } from "./query-provider";
import { EmpresaProvider } from "./empresa-provider";
import { CommandPalette } from "./command-palette";
import { AlertasFlutuantes } from "./alertas-flutuantes";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NuqsAdapter>
      <QueryProvider>
        <EmpresaProvider>
          {children}
          <CommandPalette />
          <AlertasFlutuantes />
        </EmpresaProvider>
      </QueryProvider>
    </NuqsAdapter>
  );
}
