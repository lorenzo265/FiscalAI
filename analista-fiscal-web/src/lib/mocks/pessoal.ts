import type { Empresa } from "@/lib/schemas/empresa";
import type {
  EventoEsocial,
  Funcionario,
  Holerite,
  StatusEventoEsocial,
  TipoEventoEsocial,
} from "@/lib/schemas/pessoal";
import { calcularHolerite, chaveCompetencia } from "@/lib/pessoal/calculo-folha";
import { pseudoUuid } from "@/lib/mocks/utils";

interface FuncionarioSeed {
  nome: string;
  cpf: string;
  cargo: string;
  setor: string;
  tipoContrato: Funcionario["tipoContrato"];
  jornadaSemanal: number;
  salario: number;
  genero: Funcionario["genero"];
  dataNascimento: string;
  dataAdmissao: string;
  status: Funcionario["status"];
  email: string;
  pisPasep?: string;
  dataDemissao?: string;
}

const SEEDS: FuncionarioSeed[] = [
  {
    nome: "Mariana de Souza",
    cpf: "12345678901",
    cargo: "Gerente operacional",
    setor: "Operação",
    tipoContrato: "CLT",
    jornadaSemanal: 44,
    salario: 5_800,
    genero: "F",
    dataNascimento: "1989-03-12",
    dataAdmissao: "2023-04-10",
    status: "ativo",
    email: "mariana.souza@fiscalai.demo",
    pisPasep: "12345678901",
  },
  {
    nome: "João Pedro Almeida",
    cpf: "98765432100",
    cargo: "Atendente sênior",
    setor: "Atendimento",
    tipoContrato: "CLT",
    jornadaSemanal: 44,
    salario: 2_650,
    genero: "M",
    dataNascimento: "1995-08-22",
    dataAdmissao: "2024-02-01",
    status: "ativo",
    email: "joao.almeida@fiscalai.demo",
    pisPasep: "98765432100",
  },
  {
    nome: "Beatriz Lima",
    cpf: "55544433300",
    cargo: "Analista financeiro",
    setor: "Administrativo",
    tipoContrato: "CLT",
    jornadaSemanal: 40,
    salario: 4_200,
    genero: "F",
    dataNascimento: "1992-11-04",
    dataAdmissao: "2022-09-15",
    status: "afastado",
    email: "beatriz.lima@fiscalai.demo",
    pisPasep: "55544433300",
  },
  {
    nome: "Lucas Mendes",
    cpf: "33322211100",
    cargo: "Designer freelancer",
    setor: "Marketing",
    tipoContrato: "PJ",
    jornadaSemanal: 20,
    salario: 3_500,
    genero: "M",
    dataNascimento: "1998-06-18",
    dataAdmissao: "2025-03-01",
    status: "ativo",
    email: "lucas.mendes@fiscalai.demo",
  },
];

export function gerarFuncionariosIniciais(empresa: Empresa): Funcionario[] {
  return SEEDS.map((s, i) => ({
    id: `func-${empresa.id}-${i}`,
    nome: s.nome,
    cpf: s.cpf,
    email: s.email,
    dataNascimento: s.dataNascimento,
    genero: s.genero,
    cargo: s.cargo,
    setor: s.setor,
    tipoContrato: s.tipoContrato,
    jornadaSemanal: s.jornadaSemanal,
    salario: s.salario,
    dataAdmissao: s.dataAdmissao,
    dataDemissao: s.dataDemissao,
    status: s.status,
    avatarSeed: s.cpf,
    pisPasep: s.pisPasep,
  }));
}

export function gerarHoleritesIniciais(
  funcionarios: Funcionario[],
  meses = 6
): Holerite[] {
  const hoje = new Date();
  const lista: Holerite[] = [];

  for (let m = meses - 1; m >= 0; m--) {
    const ref = new Date(hoje.getFullYear(), hoje.getMonth() - m, 1);
    const ano = ref.getFullYear();
    const mes = ref.getMonth() + 1;
    for (const f of funcionarios) {
      if (f.status === "demitido" && f.dataDemissao && f.dataDemissao < `${ano}-${String(mes).padStart(2, "0")}-01`) {
        continue;
      }
      const isCorrente = m === 0;
      const holerite = calcularHolerite({
        funcionario: f,
        ano,
        mes,
        diasTrabalhados: f.status === "afastado" && isCorrente ? 18 : 30,
        status: isCorrente ? "gerado" : "pago",
      });
      if (!isCorrente) {
        holerite.pagoEm = `${ano}-${String(mes).padStart(2, "0")}-05`;
      }
      lista.push(holerite);
    }
  }
  return lista;
}

export function gerarEventosEsocialIniciais(
  funcionarios: Funcionario[],
  holerites: Holerite[]
): EventoEsocial[] {
  const eventos: EventoEsocial[] = [];
  const hoje = new Date();

  for (const f of funcionarios) {
    const transmitidoEm = new Date(f.dataAdmissao + "T10:00:00").toISOString();
    eventos.push({
      id: `esocial-S2200-${f.id}`,
      tipo: "S-2200",
      funcionarioId: f.id,
      funcionarioNome: f.nome,
      competencia: f.dataAdmissao.slice(0, 7),
      status: "transmitido",
      recibo: `R-${pseudoUuid().slice(0, 8).toUpperCase()}`,
      transmitidoEm,
      criadoEm: transmitidoEm,
    });
  }

  // S-1200 por funcionário no mês corrente e mês anterior (alguns transmitidos, 1 com erro)
  const competenciaCorrente = chaveCompetencia(
    hoje.getFullYear(),
    hoje.getMonth() + 1
  );
  const refAnterior = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
  const competenciaAnterior = chaveCompetencia(
    refAnterior.getFullYear(),
    refAnterior.getMonth() + 1
  );

  let erroPlantado = false;
  for (const f of funcionarios) {
    const holeriteCorrente = holerites.find(
      (h) => h.funcionarioId === f.id && h.competencia === competenciaCorrente
    );
    if (!holeriteCorrente) continue;

    const status: StatusEventoEsocial =
      !erroPlantado && f.tipoContrato === "CLT"
        ? "erro"
        : f.tipoContrato === "PJ"
          ? "transmitido"
          : "pendente";

    if (status === "erro") erroPlantado = true;

    eventos.push({
      id: `esocial-S1200-${f.id}-${competenciaCorrente}`,
      tipo: "S-1200",
      funcionarioId: f.id,
      funcionarioNome: f.nome,
      competencia: competenciaCorrente,
      status,
      recibo:
        status === "transmitido"
          ? `R-${pseudoUuid().slice(0, 8).toUpperCase()}`
          : undefined,
      motivoErro:
        status === "erro"
          ? "Divergência de PIS/PASEP — confira o cadastro do trabalhador"
          : undefined,
      transmitidoEm:
        status === "transmitido" ? new Date().toISOString() : undefined,
      criadoEm: new Date().toISOString(),
    });
  }

  // Mês anterior — todos transmitidos
  for (const f of funcionarios) {
    eventos.push({
      id: `esocial-S1200-${f.id}-${competenciaAnterior}`,
      tipo: "S-1200",
      funcionarioId: f.id,
      funcionarioNome: f.nome,
      competencia: competenciaAnterior,
      status: "transmitido",
      recibo: `R-${pseudoUuid().slice(0, 8).toUpperCase()}`,
      transmitidoEm: refAnterior.toISOString(),
      criadoEm: refAnterior.toISOString(),
    });
  }

  // S-1299 do mês anterior (fechamento) transmitido
  eventos.push({
    id: `esocial-S1299-${competenciaAnterior}`,
    tipo: "S-1299",
    competencia: competenciaAnterior,
    status: "transmitido",
    recibo: `R-${pseudoUuid().slice(0, 8).toUpperCase()}`,
    transmitidoEm: refAnterior.toISOString(),
    criadoEm: refAnterior.toISOString(),
  });

  // S-2230 para a Beatriz (afastada)
  const afastada = funcionarios.find((f) => f.status === "afastado");
  if (afastada) {
    eventos.push({
      id: `esocial-S2230-${afastada.id}`,
      tipo: "S-2230",
      funcionarioId: afastada.id,
      funcionarioNome: afastada.nome,
      competencia: competenciaCorrente,
      status: "transmitido",
      recibo: `R-${pseudoUuid().slice(0, 8).toUpperCase()}`,
      transmitidoEm: new Date(
        hoje.getTime() - 7 * 24 * 60 * 60 * 1000
      ).toISOString(),
      criadoEm: new Date(
        hoje.getTime() - 7 * 24 * 60 * 60 * 1000
      ).toISOString(),
    });
  }

  return eventos;
}

export function gerarEventoAdmissaoMock(
  funcionario: Funcionario
): EventoEsocial {
  return {
    id: `esocial-S2200-${funcionario.id}-${Date.now()}`,
    tipo: "S-2200" as TipoEventoEsocial,
    funcionarioId: funcionario.id,
    funcionarioNome: funcionario.nome,
    competencia: funcionario.dataAdmissao.slice(0, 7),
    status: "transmitido",
    recibo: `R-${pseudoUuid().slice(0, 8).toUpperCase()}`,
    transmitidoEm: new Date().toISOString(),
    criadoEm: new Date().toISOString(),
  };
}
