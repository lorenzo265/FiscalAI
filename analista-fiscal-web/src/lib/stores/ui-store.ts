"use client";

import { create } from "zustand";

interface UIStore {
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;
  sidebarMobileOpen: boolean;
  setSidebarMobileOpen: (open: boolean) => void;
  assistenteSidebarOpen: boolean;
  setAssistenteSidebarOpen: (open: boolean) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  commandPaletteOpen: false,
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  toggleCommandPalette: () =>
    set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),
  sidebarMobileOpen: false,
  setSidebarMobileOpen: (open) => set({ sidebarMobileOpen: open }),
  assistenteSidebarOpen: false,
  setAssistenteSidebarOpen: (open) => set({ assistenteSidebarOpen: open }),
}));
