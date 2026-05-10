"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Calendar,
  FileText,
  Receipt,
  Sparkles,
  Wallet,
  Users,
  Settings,
  Search,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { useUIStore } from "@/lib/stores/ui-store";

interface QuickAction {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  shortcut?: string;
  group: "Navegar" | "Ações rápidas";
}

const ACTIONS: QuickAction[] = [
  { label: "Início", href: "/home", icon: Search, group: "Navegar", shortcut: "G H" },
  { label: "Apuração fiscal", href: "/fiscal", icon: Receipt, group: "Navegar", shortcut: "G F" },
  { label: "Notas fiscais", href: "/notas", icon: FileText, group: "Navegar", shortcut: "G N" },
  { label: "Contas a pagar", href: "/controles/pagar", icon: Wallet, group: "Navegar" },
  { label: "Folha de pagamento", href: "/pessoal", icon: Users, group: "Navegar" },
  { label: "Calendário fiscal", href: "/agenda", icon: Calendar, group: "Navegar" },
  { label: "Configurações", href: "/configuracoes", icon: Settings, group: "Navegar" },
  { label: "Emitir nova NF-e", href: "/notas/saida/nova", icon: FileText, group: "Ações rápidas" },
  { label: "Falar com o assistente", href: "/assistente", icon: Sparkles, group: "Ações rápidas" },
];

export function CommandPalette() {
  const open = useUIStore((s) => s.commandPaletteOpen);
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const toggle = useUIStore((s) => s.toggleCommandPalette);
  const router = useRouter();

  React.useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        toggle();
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggle]);

  const grouped = React.useMemo(() => {
    const map = new Map<string, QuickAction[]>();
    for (const a of ACTIONS) {
      const list = map.get(a.group) ?? [];
      list.push(a);
      map.set(a.group, list);
    }
    return Array.from(map.entries());
  }, []);

  function go(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Buscar telas, ações ou empresa..." />
      <CommandList>
        <CommandEmpty>Nada encontrado.</CommandEmpty>
        {grouped.map(([group, items]) => (
          <CommandGroup key={group} heading={group}>
            {items.map((a) => (
              <CommandItem key={a.href} value={`${a.label} ${a.href}`} onSelect={() => go(a.href)}>
                <a.icon className="size-4 text-[var(--color-txt-3)]" />
                <span>{a.label}</span>
                {a.shortcut ? <CommandShortcut>{a.shortcut}</CommandShortcut> : null}
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
      </CommandList>
    </CommandDialog>
  );
}
