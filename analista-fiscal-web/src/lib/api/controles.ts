/**
 * Adapter de domínio: controles / tesouraria (Onda 2 / Fase E — integração real).
 *
 * Superfície pública (`controles.*`) e assinaturas PRESERVADAS — os hooks
 * (`useBancos`, `useTransacoes`, `useConciliarTransacao`, `useContasPagarReceber`,
 * `useFluxoCaixa`, …) não mudam. A lógica de transporte vive em
 * `@/lib/controles/db-service`, que decide por chamada o que vem da API real
 * (Open Finance) e o que permanece LOCAL.
 *
 * Mapa endpoint real (descoberto por curl/OpenAPI — ver handoff):
 *   - bancos     → `GET  /v1/empresas/{id}/contas-bancarias`
 *   - transações → `GET  /v1/empresas/{id}/transacoes?conta_id=&limite=`
 *   - sync       → `POST /v1/empresas/{id}/open-finance/items/{item_uuid}/sync`
 *
 * GAPS conscientes (sem endpoint → mantidos LOCAIS, nada fingido como backend):
 *   - **conectar conta** por clique: requer widget Pluggy → Dexie local.
 *   - **conciliar** (transação ↔ lançamento contábil): a conciliação do backend
 *     é NF × banco (entidade `Match`, semântica diferente) → vínculo local.
 *   - **contas a pagar/receber** e **fluxo de caixa**: sem endpoint → Dexie /
 *     cálculo cliente. O fluxo é DERIVADO de contas + transações reais (quando há)
 *     somadas às contas a pagar/receber locais.
 *
 * Dono na integração: agente de domínio controles.
 */
import {
  conciliarTransacao,
  conectarNovaConta,
  listarContasBancarias,
  listarContasPagarReceber,
  listarTodasTransacoes,
  listarTransacoes,
  marcarContaPaga,
  obterContaBancaria,
  removerContaPagarReceber,
  sincronizarConta,
  adicionarContaPagarReceber,
  atualizarContaPagarReceber,
  atualizarStatusVencidos,
} from "@/lib/controles/db-service";
import { gerarFluxoCaixa } from "@/lib/mocks/controles";
import { ApiError } from "@/lib/http";
import type {
  ContaBancaria,
  ContaPagarReceber,
  FluxoCaixa,
  TransacaoBancaria,
} from "@/lib/schemas/controles";
import type { Empresa } from "@/lib/schemas/empresa";

/** Traduz `ApiError.codigo` em mensagem amigável (nunca vaza código cru). */
export function mensagemAmigavelControles(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Não foi possível carregar seus controles agora. Tente novamente.";
  }
  switch (err.codigo) {
    case "EmpresaNaoEncontrada":
    case "EmpresaNaoSelecionada":
      return "Selecione uma empresa para ver suas contas e movimentações.";
    case "SemPermissao":
      return "Você não tem permissão para acessar estes controles.";
    case "PluggyItemNaoEncontrado":
    case "ContaBancariaNaoEncontrada":
      return "Conta bancária não encontrada. Reconecte-a pelo Open Finance.";
    case "PluggyIndisponivel":
    case "FalhaDeRede":
      return "Não conseguimos falar com o Open Finance agora. Tente novamente em instantes.";
    default:
      return err.mensagem || "Não foi possível carregar seus controles agora.";
  }
}

export const controles = {
  listarBancos: (): Promise<ContaBancaria[]> => listarContasBancarias(),
  obterBanco: (id: string): Promise<ContaBancaria | undefined> =>
    obterContaBancaria(id),
  sincronizarBanco: (id: string): Promise<ContaBancaria | undefined> =>
    sincronizarConta(id),
  conectarBanco: (empresa: Empresa, bancoId: string): Promise<ContaBancaria> =>
    conectarNovaConta(empresa, bancoId),
  listarTransacoes: (contaId: string): Promise<TransacaoBancaria[]> =>
    listarTransacoes(contaId),
  listarTodasTransacoes: (): Promise<TransacaoBancaria[]> =>
    listarTodasTransacoes(),
  conciliarTransacao: (
    transacaoId: string,
    lancamentoId: string | null
  ): Promise<void> => conciliarTransacao(transacaoId, lancamentoId),
  listarContasPagarReceber: async (): Promise<ContaPagarReceber[]> => {
    await atualizarStatusVencidos();
    return listarContasPagarReceber();
  },
  adicionarContaPagarReceber: (conta: ContaPagarReceber): Promise<void> =>
    adicionarContaPagarReceber(conta),
  atualizarContaPagarReceber: (conta: ContaPagarReceber): Promise<void> =>
    atualizarContaPagarReceber(conta),
  removerContaPagarReceber: (id: string): Promise<void> =>
    removerContaPagarReceber(id),
  marcarContaPaga: (id: string, pagoEm: string): Promise<void> =>
    marcarContaPaga(id, pagoEm),
  /**
   * Fluxo de caixa — DERIVADO client-side (sem endpoint backend). Combina saldo
   * das contas reais + transações reais (passado) com contas a pagar/receber
   * locais (futuro projetado). Honesto: o projetado vem de dado local.
   */
  fluxoCaixa: async (dias = 90): Promise<FluxoCaixa> => {
    await atualizarStatusVencidos();
    const [contas, contasPR, transacoes] = await Promise.all([
      listarContasBancarias(),
      listarContasPagarReceber(),
      listarTodasTransacoes(),
    ]);
    const saldoHoje = contas.reduce((acc, c) => acc + c.saldo, 0);
    return gerarFluxoCaixa({ saldoHoje, contas: contasPR, transacoes }, dias);
  },
};
