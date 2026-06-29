/**
 * Adapter de domínio: assistente (Onda 2 — integração HTTP real).
 *
 * `enviarPergunta` fala com o backend FastAPI:
 *   POST /v1/empresas/{empresa_id}/assistente/perguntar
 * O backend roda o LLM (Ollama local / Gemini) com CITAÇÃO OBRIGATÓRIA e
 * re-check determinístico (§8.5 + §8.6). A resposta traz `{resposta, citacoes,
 * provider_usado, encaminhar_marketplace, …}` — citações no formato
 * `{fato_id, trecho_citado}` (sem categoria de domínio).
 *
 * Persistência de conversa: o backend NÃO expõe endpoint de histórico de chat
 * (o módulo `memoria` é grafo de fatos, não transcrição). Por isso o HISTÓRICO
 * é LOCAL (Dexie) — `listarMensagens`/`limparHistorico` continuam no db-service.
 * Pergunta e resposta reais são gravadas no Dexie para a tela reexibir.
 *
 * Citação: preservada e exibida (a tela mostra a fonte). Re-check: NÃO exibimos
 * valor/stat que a resposta não sustenta — só renderizamos o texto + as citações
 * que o backend retornou; nenhum bloco monetário é fabricado no front.
 */
import {
  adicionarMensagem,
  limparMensagens,
  listarMensagens,
} from "@/lib/assistente/db-service";
import { fetchJson, ApiError } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import {
  respostaAssistenteSchema,
  type Bloco,
  type Citacao,
  type MensagemAssistente,
  type RespostaAssistente,
} from "@/lib/schemas/assistente";
import type { Empresa } from "@/lib/schemas/empresa";

function idMensagem(prefixo: string): string {
  const rand = Math.random().toString(36).slice(2, 12);
  return `msg-${prefixo}-${rand}`;
}

/** Mapeia o erro de domínio do backend para texto amigável (nunca vaza `codigo`). */
export function mensagemAmigavelAssistente(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.codigo) {
      case "LLMIndisponivel":
        return "O assistente está temporariamente indisponível. Tente novamente em instantes.";
      case "FalhaDeRede":
        return "Não consegui falar com o assistente. Verifique sua conexão e tente de novo.";
      case "SemPermissao":
        return "Você não tem permissão para usar o assistente nesta empresa.";
      case "EmpresaNaoEncontrada":
        return "Empresa não encontrada. Selecione uma empresa ativa e tente de novo.";
      default:
        // 5xx / timeouts genéricos → tratar como indisponibilidade.
        if (err.status >= 500 || err.status === 0) {
          return "O assistente está temporariamente indisponível. Tente novamente em instantes.";
        }
        return "Não consegui processar sua pergunta agora. Tente reformular ou tente mais tarde.";
    }
  }
  return "Não consegui processar sua pergunta agora. Tente novamente.";
}

/**
 * Converte a resposta crua do backend numa `MensagemAssistente` do front.
 * - texto = `resposta` (o LLM já responde em PT-BR, com re-check determinístico).
 * - citações = `{fato_id, trecho_citado}` → `{tipo:"fonte", rotulo:trecho_citado}`.
 *   (preservadas — princípio §8.5; sem rota, pois o backend não fornece uma).
 * - encaminhar_marketplace → bloco de alerta (sem inventar parceiro).
 */
function mapearResposta(
  raw: RespostaAssistente,
  criadoEm: string
): MensagemAssistente {
  const citacoes: Citacao[] = raw.citacoes.map((c) => ({
    tipo: "fonte",
    rotulo: c.trechoCitado,
  }));

  const blocos: Bloco[] = [];
  if (raw.encaminharMarketplace) {
    const categoria =
      raw.categoriaMarketplaceSugerida ?? raw.categoriaMarketplace ?? null;
    blocos.push({
      tipo: "alerta",
      tom: "info",
      titulo: "Isso é melhor com um contador parceiro",
      descricao: categoria
        ? `Esse tema (${categoria}) está fora do que posso resolver direto. Posso te conectar a um contador parceiro.`
        : "Esse tema está fora do que posso resolver direto. Posso te conectar a um contador parceiro.",
    });
  }

  return {
    id: idMensagem("a"),
    role: "assistant",
    texto: raw.resposta,
    blocos,
    citacoes,
    sugestoes: [],
    criadoEm,
  };
}

export const assistente = {
  listarMensagens: (): Promise<MensagemAssistente[]> => listarMensagens(),

  enviarPergunta: async (
    _empresa: Empresa,
    pergunta: string
  ): Promise<{
    pergunta: MensagemAssistente;
    resposta: MensagemAssistente;
  }> => {
    const empresaId = getEmpresaIdAtiva();
    if (!empresaId) {
      throw new ApiError(
        0,
        "EmpresaNaoEncontrada",
        "Nenhuma empresa ativa selecionada."
      );
    }

    const textoPergunta = pergunta.trim();
    const msgPergunta: MensagemAssistente = {
      id: idMensagem("u"),
      role: "user",
      texto: textoPergunta,
      blocos: [],
      citacoes: [],
      sugestoes: [],
      criadoEm: new Date().toISOString(),
    };
    // Persiste a pergunta antes da chamada — se o LLM cair (503), a pergunta
    // do usuário não some do histórico local.
    await adicionarMensagem(msgPergunta);

    const raw = await fetchJson<RespostaAssistente>(
      `/empresas/${empresaId}/assistente/perguntar`,
      respostaAssistenteSchema,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pergunta: textoPergunta }),
      },
      // LLM é lento; 60s evita o chat ficar "digitando" para sempre se o
      // backend não tiver modelo configurado. POST → sem retry (não re-pergunta).
      { timeoutMs: 60_000 }
    );

    const msgResposta = mapearResposta(raw, new Date().toISOString());
    await adicionarMensagem(msgResposta);

    return { pergunta: msgPergunta, resposta: msgResposta };
  },

  limparHistorico: (): Promise<void> => limparMensagens(),
};
