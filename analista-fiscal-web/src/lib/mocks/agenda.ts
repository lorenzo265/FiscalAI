import type { EventoAgenda } from "@/lib/schemas/agenda";
import type { Empresa } from "@/lib/schemas/empresa";
import { calcularDAS } from "@/lib/fiscal/calcula-das";

export function gerarEventosMesMock(empresa: Empresa, hoje: Date = new Date()): EventoAgenda[] {
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth();
  const fat12 = empresa.faturamento12m;
  const anexo = empresa.anexoSimples ?? "III";
  const valorDAS = calcularDAS({
    rbt12: fat12,
    receitaMes: fat12 / 12,
    anexo,
  }).valorDAS;
  const fgts = (fat12 / 12) * 0.018;
  const eventos: EventoAgenda[] = [];

  const mesAnterior = new Date(ano, mes, 0);

  // FGTS dia 7
  eventos.push({
    id: `fgts-${ano}-${mes}`,
    data: dataIso(ano, mes, 7),
    titulo: "FGTS",
    descricao: `Recolhimento da competência ${mesAnterior.getMonth() + 1}/${mesAnterior.getFullYear()}.`,
    tipo: "folha",
    status: diaJaPassou(ano, mes, 7, hoje) ? "pago" : "pendente",
    valor: Math.round(fgts),
    rota: "/pessoal",
  });

  // DCTFWeb dia 15
  eventos.push({
    id: `dctf-${ano}-${mes}`,
    data: dataIso(ano, mes, 15),
    titulo: "DCTFWeb",
    descricao: "Declaração que substitui a GFIP — envio mensal.",
    tipo: "obrigacao_acessoria",
    status: diaJaPassou(ano, mes, 15, hoje) ? "pago" : "pendente",
    rota: "/fiscal",
  });

  // INSS dia 20
  eventos.push({
    id: `inss-${ano}-${mes}`,
    data: dataIso(ano, mes, 20),
    titulo: "INSS Patronal",
    descricao: `Contribuição previdenciária da competência ${mesAnterior.getMonth() + 1}.`,
    tipo: "imposto",
    status: diaJaPassou(ano, mes, 20, hoje) ? "pago" : "pendente",
    valor: Math.round((fat12 / 12) * 0.04),
    rota: "/fiscal/guias",
  });

  // DAS dia 20
  eventos.push({
    id: `das-${ano}-${mes}`,
    data: dataIso(ano, mes, 20),
    titulo: "DAS Simples Nacional",
    descricao: `Apuração de ${mesAnterior.getMonth() + 1}/${mesAnterior.getFullYear()}.`,
    tipo: "imposto",
    status: diaJaPassou(ano, mes, 20, hoje) ? "pago" : "pendente",
    valor: Math.round(valorDAS),
    rota: "/fiscal/guias",
  });

  // PGDAS-D último dia
  const ultimoDia = new Date(ano, mes + 1, 0).getDate();
  eventos.push({
    id: `pgdasd-${ano}-${mes}`,
    data: dataIso(ano, mes, ultimoDia),
    titulo: "PGDAS-D",
    descricao: "Declaração mensal do Simples Nacional.",
    tipo: "obrigacao_acessoria",
    status: "pendente",
    rota: "/fiscal",
  });

  // eSocial dia 12
  eventos.push({
    id: `esocial-${ano}-${mes}`,
    data: dataIso(ano, mes, 12),
    titulo: "Eventos eSocial",
    descricao: "Transmissão de S-1200 (folha) e S-1210 (pagamentos).",
    tipo: "esocial",
    status: diaJaPassou(ano, mes, 12, hoje) ? "pago" : "pendente",
    rota: "/pessoal/esocial",
  });

  return eventos;
}

function dataIso(ano: number, mesIdx: number, dia: number): string {
  const m = String(mesIdx + 1).padStart(2, "0");
  const d = String(dia).padStart(2, "0");
  return `${ano}-${m}-${d}`;
}

function diaJaPassou(ano: number, mesIdx: number, dia: number, hoje: Date): boolean {
  const dt = new Date(ano, mesIdx, dia);
  return dt.getTime() < hoje.getTime();
}
