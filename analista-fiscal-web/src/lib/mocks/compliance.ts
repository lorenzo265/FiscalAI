import type { Empresa } from "@/lib/schemas/empresa";
import type {
  Certidao,
  Intimacao,
  Parcelamento,
  StatusCertidao,
  TipoCertidao,
} from "@/lib/schemas/compliance";
import { pseudoUuid } from "@/lib/mocks/utils";

const DIA_MS = 24 * 60 * 60 * 1000;

function isoDia(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function gerarNumeroCertidao(prefixo: string): string {
  const seq = Math.floor(100000 + Math.random() * 899999);
  const ano = new Date().getFullYear();
  return `${prefixo}.${seq}/${ano}`;
}

interface CertidaoSeed {
  tipo: TipoCertidao;
  emitidaPor: string;
  diasAteVencer: number;
  prefixoNumero: string;
}

const SEEDS: CertidaoSeed[] = [
  {
    tipo: "CND_FEDERAL",
    emitidaPor: "Receita Federal · PGFN",
    diasAteVencer: 142,
    prefixoNumero: "CND",
  },
  {
    tipo: "CRF_FGTS",
    emitidaPor: "Caixa Econômica Federal",
    diasAteVencer: 18, // amber em <30d
    prefixoNumero: "CRF",
  },
  {
    tipo: "CNDT_TRABALHISTA",
    emitidaPor: "Tribunal Superior do Trabalho",
    diasAteVencer: 121,
    prefixoNumero: "CNDT",
  },
];

export function gerarCertidoesIniciais(empresa: Empresa): Certidao[] {
  const hoje = new Date();
  return SEEDS.map((seed, i) => {
    const vencimento = new Date(hoje.getTime() + seed.diasAteVencer * DIA_MS);
    const emitidaEm = new Date(
      vencimento.getTime() - validadeDias(seed.tipo) * DIA_MS
    );
    const status: StatusCertidao =
      seed.diasAteVencer <= 0
        ? "vencida"
        : seed.diasAteVencer <= 30
          ? "vence_em_breve"
          : "vigente";
    return {
      id: `cert-${empresa.id}-${seed.tipo}-${i}`,
      tipo: seed.tipo,
      numero: gerarNumeroCertidao(seed.prefixoNumero),
      emitidaEm: isoDia(emitidaEm),
      vencimento: isoDia(vencimento),
      status,
      emitidaPor: seed.emitidaPor,
    };
  });
}

export function validadeDias(tipo: TipoCertidao): number {
  switch (tipo) {
    case "CND_FEDERAL":
      return 180;
    case "CRF_FGTS":
      return 30;
    case "CNDT_TRABALHISTA":
      return 180;
    case "CND_ESTADUAL":
      return 90;
    case "CND_MUNICIPAL":
      return 90;
  }
}

export function calcularStatusCertidao(
  vencimento: string,
  hoje: Date = new Date()
): StatusCertidao {
  const venc = new Date(vencimento).getTime();
  const dias = (venc - hoje.getTime()) / DIA_MS;
  if (dias < 0) return "vencida";
  if (dias <= 30) return "vence_em_breve";
  return "vigente";
}

export function gerarCertidaoRenovada(antiga: Certidao): Certidao {
  const hoje = new Date();
  const validade = validadeDias(antiga.tipo);
  const novoVencimento = new Date(hoje.getTime() + validade * DIA_MS);
  return {
    ...antiga,
    id: `cert-${pseudoUuid().slice(0, 8)}`,
    numero: gerarNumeroCertidao(antiga.numero.split(".")[0] ?? "CND"),
    emitidaEm: isoDia(hoje),
    vencimento: isoDia(novoVencimento),
    status: "vigente",
  };
}

const TEXTO_INTIMACAO_MOCK = `Prezado contribuinte,

Foi identificada divergência nos valores declarados na DCTFWeb da competência ${formatarMesPassado()} em relação ao recolhimento efetivamente realizado por meio da DARF correspondente.

Solicitamos que, no prazo de 30 (trinta) dias contados do recebimento desta intimação, sejam apresentados:

1. Cópia digital da DARF de pagamento;
2. Demonstrativo de cálculo das contribuições previdenciárias do período;
3. Esclarecimento, por escrito, sobre a divergência apontada.

A não-resposta no prazo legal poderá implicar lançamento de ofício, multa de mora e juros segundo a legislação vigente.

Cordialmente,
Auditoria Fiscal — Receita Federal do Brasil`;

function formatarMesPassado(): string {
  const hoje = new Date();
  const ref = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
  const meses = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
  ];
  return `${meses[ref.getMonth()]}/${ref.getFullYear()}`;
}

export function gerarIntimacoesIniciais(empresa: Empresa): Intimacao[] {
  const hoje = new Date();
  const recebido = new Date(hoje.getTime() - 4 * DIA_MS);
  const prazo = new Date(hoje.getTime() + 26 * DIA_MS);
  return [
    {
      id: `intim-${empresa.id}-01`,
      protocolo: `RFB-${new Date().getFullYear()}-${Math.floor(100000 + Math.random() * 899999)}`,
      orgao: "RFB",
      assunto: "Divergência DCTFWeb x DARF",
      texto: TEXTO_INTIMACAO_MOCK,
      recebidoEm: recebido.toISOString(),
      prazoResposta: isoDia(prazo),
      status: "lida",
      enviadoContador: false,
    },
  ];
}

export function gerarParcelamentosIniciais(_empresa: Empresa): Parcelamento[] {
  // Plano: empresa demo limpa, sem débitos parcelados
  return [];
}
