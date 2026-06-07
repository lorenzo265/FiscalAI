/**
 * Adapter de domínio: pessoal (Onda 2 / Fase E — integração com a API real).
 *
 * As assinaturas de `pessoal.*` são preservadas (as telas e os hooks
 * `use-pessoal` dependem delas). A implementação delega ao
 * `@/lib/pessoal/db-service`, que fala com o backend FastAPI:
 *   - Funcionários / folha / holerites → endpoints reais
 *     (`/v1/empresas/{id}/funcionarios`, `…/folhas/{competencia}/fechar`,
 *     `…/folhas/{competencia}/holerites`).
 *   - Eventos eSocial → endpoints reais (`…/esocial/eventos`, `…/assinar`,
 *     `…/transmissao/lotes`). Gerados ao fechar a folha (S-1200 por holerite).
 *     Transmissão real é gated (sem cert A1 → 412) e tratada com mensagem
 *     honesta — nunca simula sucesso.
 *
 * `mensagemAmigavelPessoal` traduz `ApiError.codigo` em texto para o dono da
 * PME — nunca vaza o código cru nem expõe CPF/dado sensível.
 *
 * Dono na integração: agente de domínio pessoal.
 */
import {
  adicionarEventoEsocial,
  adicionarFuncionario,
  atualizarStatusEvento,
  gerarHoleritesDoMes,
  listarEventosEsocial,
  listarFuncionarios,
  listarHolerites,
  listarHoleritesDoMes,
  obterFuncionario,
  transmitirEventosDoMes,
} from "@/lib/pessoal/db-service";
import { ApiError } from "@/lib/http";
import type {
  EventoEsocial,
  Funcionario,
  Holerite,
  StatusEventoEsocial,
} from "@/lib/schemas/pessoal";

/** Traduz `ApiError.codigo` em mensagem amigável (nunca vaza código cru). */
export function mensagemAmigavelPessoal(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Não foi possível concluir a operação da folha agora. Tente novamente.";
  }
  switch (err.codigo) {
    case "EmpresaNaoSelecionada":
      return "Selecione uma empresa para gerenciar a folha.";
    case "EmpresaNaoEncontrada":
      return "Empresa não encontrada. Selecione uma empresa ativa.";
    case "FuncionarioNaoEncontrado":
      return "Funcionário não encontrado.";
    case "CpfJaCadastrado":
      return "Já existe um funcionário com este CPF.";
    case "FolhaNaoEncontrada":
      return "A folha deste mês ainda não foi fechada.";
    case "FolhaJaFechada":
      return "A folha deste mês já foi fechada.";
    case "SemFuncionariosAtivos":
      return "Cadastre ao menos um funcionário ativo antes de fechar a folha.";
    case "TabelaTributariaAusente":
      return "Tabela de INSS/IRRF indisponível para esta competência.";
    case "EsocialAssinaturaIndisponivel":
    case "EsocialTransmissaoDesativada":
      return "A transmissão ao eSocial ainda não está habilitada — requer certificado digital A1. Os eventos ficam preparados até a habilitação.";
    case "EsocialEventoNaoEncontrado":
      return "Evento do eSocial não encontrado.";
    case "EsocialLoteInvalido":
      return "Não há eventos prontos para transmitir ao eSocial.";
    default:
      return (
        err.mensagem ||
        "Não foi possível concluir a operação da folha agora. Tente novamente."
      );
  }
}

export const pessoal = {
  listarFuncionarios: (): Promise<Funcionario[]> => listarFuncionarios(),
  obterFuncionario: (id: string): Promise<Funcionario | undefined> =>
    obterFuncionario(id),
  adicionarFuncionario: (f: Funcionario): Promise<void> =>
    adicionarFuncionario(f),
  listarHolerites: (): Promise<Holerite[]> => listarHolerites(),
  listarHoleritesDoMes: (ano: number, mes: number): Promise<Holerite[]> =>
    listarHoleritesDoMes(ano, mes),
  gerarHoleritesDoMes: (ano: number, mes: number): Promise<Holerite[]> =>
    gerarHoleritesDoMes(ano, mes),
  listarEventosEsocial: (): Promise<EventoEsocial[]> => listarEventosEsocial(),
  adicionarEventoEsocial: (evento: EventoEsocial): Promise<void> =>
    adicionarEventoEsocial(evento),
  atualizarStatusEvento: (
    id: string,
    status: StatusEventoEsocial,
    extras?: { recibo?: string; motivoErro?: string }
  ): Promise<void> => atualizarStatusEvento(id, status, extras),
  transmitirEventosDoMes: (
    ano: number,
    mes: number
  ): Promise<{ transmitidos: number }> => transmitirEventosDoMes(ano, mes),
};
