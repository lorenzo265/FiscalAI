import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Receipt,
  FileText,
  BookOpen,
  Wallet,
  Users,
  PieChart,
  ShieldCheck,
  Calendar,
  Sparkles,
  Lightbulb,
  Settings,
} from "lucide-react";
import type { RegimeTributario } from "@/lib/schemas/empresa";

export type ModuloId =
  | "home"
  | "fiscal"
  | "notas"
  | "contabil"
  | "controles"
  | "pessoal"
  | "relatorios"
  | "compliance"
  | "agenda"
  | "advisor"
  | "assistente"
  | "configuracoes";

export interface SidebarItem {
  id: ModuloId;
  label: string;
  href: string;
  icon: LucideIcon;
  group: "principal" | "operacional" | "ferramentas" | "config";
}

export const SIDEBAR_ITEMS: SidebarItem[] = [
  { id: "home", label: "Início", href: "/home", icon: LayoutDashboard, group: "principal" },
  { id: "fiscal", label: "Fiscal", href: "/fiscal", icon: Receipt, group: "operacional" },
  { id: "notas", label: "Notas", href: "/notas", icon: FileText, group: "operacional" },
  { id: "contabil", label: "Contábil", href: "/contabil", icon: BookOpen, group: "operacional" },
  { id: "controles", label: "Controles", href: "/controles", icon: Wallet, group: "operacional" },
  { id: "pessoal", label: "Pessoal", href: "/pessoal", icon: Users, group: "operacional" },
  {
    id: "relatorios",
    label: "Relatórios",
    href: "/relatorios/dre",
    icon: PieChart,
    group: "ferramentas",
  },
  {
    id: "compliance",
    label: "Compliance",
    href: "/compliance",
    icon: ShieldCheck,
    group: "ferramentas",
  },
  { id: "agenda", label: "Agenda", href: "/agenda", icon: Calendar, group: "ferramentas" },
  {
    id: "advisor",
    label: "Consultor",
    href: "/advisor",
    icon: Lightbulb,
    group: "ferramentas",
  },
  {
    id: "assistente",
    label: "Assistente",
    href: "/assistente",
    icon: Sparkles,
    group: "ferramentas",
  },
  {
    id: "configuracoes",
    label: "Configurações",
    href: "/configuracoes",
    icon: Settings,
    group: "config",
  },
];

const MODULOS_POR_REGIME: Record<RegimeTributario, ModuloId[]> = {
  MEI: ["home", "notas", "fiscal", "agenda", "compliance", "configuracoes"],
  SIMPLES_NACIONAL: [
    "home",
    "fiscal",
    "notas",
    "contabil",
    "controles",
    "pessoal",
    "relatorios",
    "compliance",
    "agenda",
    "advisor",
    "assistente",
    "configuracoes",
  ],
  LUCRO_PRESUMIDO: [
    "home",
    "fiscal",
    "notas",
    "contabil",
    "controles",
    "pessoal",
    "relatorios",
    "compliance",
    "agenda",
    "advisor",
    "assistente",
    "configuracoes",
  ],
  LUCRO_REAL: [
    "home",
    "fiscal",
    "notas",
    "contabil",
    "controles",
    "pessoal",
    "relatorios",
    "compliance",
    "agenda",
    "advisor",
    "assistente",
    "configuracoes",
  ],
};

export function moduloDisponivel(modulo: ModuloId, regime: RegimeTributario): boolean {
  return MODULOS_POR_REGIME[regime].includes(modulo);
}

export const GROUP_LABELS: Record<SidebarItem["group"], string> = {
  principal: "Painel",
  operacional: "Operação",
  ferramentas: "Ferramentas",
  config: "Conta",
};
