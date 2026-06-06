"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  AnexoSimples,
  RegimeTributario,
  Socio,
} from "@/lib/schemas/empresa";
import type { CnpjLookupResponse } from "@/lib/schemas/cnpj-lookup";
import type { Empresa } from "@/lib/schemas/empresa";

export interface BancoConectandoState {
  id: string;
  banco: string;
  apelido: string;
  saldo: number;
  logoVar: string;
}

export interface OnboardingState {
  passo: number;
  // Passo 1
  cnpj: string;
  dadosReceita: CnpjLookupResponse | null;
  // Empresa já criada no backend pelo onboarding (POST /v1/empresas/onboarding).
  empresaCriada: Empresa | null;
  // Passo 2
  regime: RegimeTributario | null;
  anexoSimples: AnexoSimples | null;
  faturamento12m: number;
  // Passo 3
  certificadoNome: string | null;
  certificadoSenha: string | null;
  certificadoPulado: boolean;
  // Passo 4
  bancosConectados: BancoConectandoState[];
  // Sócios derivados
  socios: Socio[];
  setPasso: (n: number) => void;
  proximo: () => void;
  voltar: () => void;
  setCnpj: (v: string) => void;
  setDadosReceita: (r: CnpjLookupResponse | null) => void;
  setEmpresaCriada: (e: Empresa | null) => void;
  setRegime: (r: RegimeTributario) => void;
  setAnexoSimples: (a: AnexoSimples) => void;
  setFaturamento12m: (v: number) => void;
  setCertificado: (nome: string, senha: string) => void;
  marcarCertificadoPulado: () => void;
  conectarBanco: (b: BancoConectandoState) => void;
  desconectarBanco: (id: string) => void;
  setSocios: (s: Socio[]) => void;
  reset: () => void;
}

const TOTAL_PASSOS = 5;

const estadoInicial = {
  passo: 1,
  cnpj: "",
  dadosReceita: null,
  empresaCriada: null,
  regime: null,
  anexoSimples: null,
  faturamento12m: 0,
  certificadoNome: null,
  certificadoSenha: null,
  certificadoPulado: false,
  bancosConectados: [] as BancoConectandoState[],
  socios: [] as Socio[],
};

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      ...estadoInicial,
      setPasso: (n) =>
        set({ passo: Math.max(1, Math.min(TOTAL_PASSOS, n)) }),
      proximo: () => set({ passo: Math.min(TOTAL_PASSOS, get().passo + 1) }),
      voltar: () => set({ passo: Math.max(1, get().passo - 1) }),
      setCnpj: (v) => set({ cnpj: v }),
      setDadosReceita: (r) =>
        set({
          dadosReceita: r,
          socios: r?.socios ?? [],
        }),
      setEmpresaCriada: (e) => set({ empresaCriada: e }),
      setRegime: (r) => set({ regime: r }),
      setAnexoSimples: (a) => set({ anexoSimples: a }),
      setFaturamento12m: (v) => set({ faturamento12m: v }),
      setCertificado: (nome, senha) =>
        set({ certificadoNome: nome, certificadoSenha: senha, certificadoPulado: false }),
      marcarCertificadoPulado: () =>
        set({ certificadoPulado: true, certificadoNome: null, certificadoSenha: null }),
      conectarBanco: (b) =>
        set((s) =>
          s.bancosConectados.find((x) => x.id === b.id)
            ? s
            : { bancosConectados: [...s.bancosConectados, b] }
        ),
      desconectarBanco: (id) =>
        set((s) => ({
          bancosConectados: s.bancosConectados.filter((b) => b.id !== id),
        })),
      setSocios: (s) => set({ socios: s }),
      reset: () => set({ ...estadoInicial }),
    }),
    {
      name: "analista-fiscal:onboarding-wizard",
    }
  )
);

export const ONBOARDING_TOTAL_PASSOS = TOTAL_PASSOS;
