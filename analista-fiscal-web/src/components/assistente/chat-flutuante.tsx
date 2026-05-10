"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { ArrowUpRight, MessageCircle, Sparkles } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ChatShell } from "@/components/assistente/chat-shell";
import { cn } from "@/lib/utils";

export function ChatFlutuante() {
  const pathname = usePathname();
  const [aberto, setAberto] = React.useState(false);

  const naPaginaDoAssistente = pathname?.startsWith("/assistente");
  if (naPaginaDoAssistente) return null;

  return (
    <>
      <Button
        type="button"
        onClick={() => setAberto(true)}
        aria-label="Abrir assistente"
        className={cn(
          "fixed bottom-5 right-5 z-40 h-12 px-4 rounded-full shadow-lg",
          "flex items-center gap-2"
        )}
      >
        <MessageCircle className="size-4" />
        <span className="hidden md:inline">Perguntar</span>
        <span
          className="size-1.5 rounded-full"
          style={{ background: "var(--color-lime)" }}
          aria-hidden
        />
      </Button>

      <Sheet open={aberto} onOpenChange={setAberto}>
        <SheetContent
          side="right"
          className="p-0 sm:max-w-md w-full flex flex-col gap-0 max-h-screen"
        >
          <SheetHeader
            className="px-4 py-3 border-b"
            style={{ borderColor: "var(--color-line)" }}
          >
            <SheetTitle className="flex items-center gap-2 text-sm">
              <span
                className="size-7 rounded-full grid place-items-center border"
                style={{
                  background: "var(--color-lime-d)",
                  borderColor: "rgba(163,255,107,0.32)",
                  color: "var(--color-lime)",
                }}
                aria-hidden
              >
                <Sparkles className="size-3.5" />
              </span>
              Assistente
            </SheetTitle>
            <SheetDescription className="text-xs">
              Pergunta rápida sobre tributos, fluxo, certidões.
            </SheetDescription>
          </SheetHeader>

          <div className="flex-1 min-h-0">
            <ChatShell compacto />
          </div>

          <div
            className="px-4 py-2.5 border-t flex items-center justify-between"
            style={{ borderColor: "var(--color-line)" }}
          >
            <span className="text-[10px] mono uppercase tracking-[0.16em] text-[var(--color-txt-3)]">
              Mock · respostas simuladas
            </span>
            <Button
              asChild
              variant="ghost"
              onClick={() => setAberto(false)}
              className="text-xs"
            >
              <Link href="/assistente">
                Abrir página completa <ArrowUpRight className="size-3.5" />
              </Link>
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
