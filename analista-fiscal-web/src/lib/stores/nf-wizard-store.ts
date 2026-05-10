import { create } from "zustand";
import type {
  Contraparte,
  FormaPagamento,
  ItemNota,
} from "@/lib/schemas/nota";

export interface NfDraft {
  contraparte: Contraparte | null;
  itens: ItemNota[];
  pagamento: {
    forma: FormaPagamento;
    vencimento: string;
    parcelas: number;
  };
  observacao: string;
}

interface State extends NfDraft {
  passo: number;
  setPasso: (n: number) => void;
  proximo: () => void;
  voltar: () => void;
  setContraparte: (c: Contraparte | null) => void;
  adicionarItem: (item: ItemNota) => void;
  removerItem: (id: string) => void;
  atualizarItem: (id: string, patch: Partial<ItemNota>) => void;
  setPagamento: (p: Partial<NfDraft["pagamento"]>) => void;
  setObservacao: (s: string) => void;
  resetar: () => void;
}

const ESTADO_INICIAL: NfDraft & { passo: number } = {
  passo: 1,
  contraparte: null,
  itens: [],
  pagamento: {
    forma: "pix",
    vencimento: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000)
      .toISOString()
      .slice(0, 10),
    parcelas: 1,
  },
  observacao: "",
};

export const useNfWizardStore = create<State>((set) => ({
  ...ESTADO_INICIAL,
  setPasso: (passo) => set({ passo }),
  proximo: () => set((s) => ({ passo: Math.min(4, s.passo + 1) })),
  voltar: () => set((s) => ({ passo: Math.max(1, s.passo - 1) })),
  setContraparte: (contraparte) => set({ contraparte }),
  adicionarItem: (item) => set((s) => ({ itens: [...s.itens, item] })),
  removerItem: (id) =>
    set((s) => ({ itens: s.itens.filter((i) => i.id !== id) })),
  atualizarItem: (id, patch) =>
    set((s) => ({
      itens: s.itens.map((i) => (i.id === id ? { ...i, ...patch } : i)),
    })),
  setPagamento: (p) =>
    set((s) => ({ pagamento: { ...s.pagamento, ...p } })),
  setObservacao: (observacao) => set({ observacao }),
  resetar: () => set({ ...ESTADO_INICIAL }),
}));
