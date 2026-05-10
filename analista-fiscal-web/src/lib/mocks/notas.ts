import type { Empresa } from "@/lib/schemas/empresa";
import type {
  Contraparte,
  NotaFiscal,
  StatusNota,
} from "@/lib/schemas/nota";
import { CATALOGO_PRODUTOS } from "@/lib/mocks/seeds/catalogo-produtos";
import { CONTRAPARTES_MOCK } from "@/lib/mocks/seeds/contrapartes";
import { calcularImpostosItem, totalizarNota } from "@/lib/notas/impostos";
import { montarChaveNFe } from "@/lib/notas/chave";

export function gerarNotasIniciais(empresa: Empresa, total = 24): NotaFiscal[] {
  const notas: NotaFiscal[] = [];
  const hoje = new Date();
  for (let i = 0; i < total; i++) {
    const dias = Math.floor(i * 4 + (i % 3));
    const data = new Date(hoje.getTime() - dias * 24 * 60 * 60 * 1000);
    const numero = total - i;
    const tipo: NotaFiscal["tipo"] = i % 5 === 0 ? "entrada" : "saida";
    const contraparte = CONTRAPARTES_MOCK[i % CONTRAPARTES_MOCK.length]!;
    const produto = CATALOGO_PRODUTOS[i % CATALOGO_PRODUTOS.length]!;
    const qtd = produto.tipo === "produto" ? (i % 3) + 1 : 1;
    const item = calcularImpostosItem({
      empresa,
      contraparte,
      entrada: {
        produto,
        descricao: produto.descricao,
        unidade: produto.unidade,
        quantidade: qtd,
        valorUnitario: produto.precoSugerido * (0.95 + (i % 7) * 0.015),
      },
    });
    const totais = totalizarNota([item]);
    const status: StatusNota =
      i === 0 ? "autorizada" : i % 11 === 0 ? "cancelada" : "autorizada";

    const chave = montarChaveNFe({
      uf: empresa.uf,
      ano: data.getFullYear(),
      mes: data.getMonth() + 1,
      cnpj: empresa.cnpj,
      numero,
    });

    const nota: NotaFiscal = {
      id: chave,
      chave,
      numero: String(numero).padStart(9, "0"),
      serie: "001",
      tipo,
      status,
      manifesto: tipo === "entrada" ? (i % 3 === 0 ? "pendente_manifesto" : "ciencia") : undefined,
      emitidaEm: data.toISOString(),
      cnpjEmitente: tipo === "saida" ? empresa.cnpj : contraparte.documento,
      razaoEmitente: tipo === "saida" ? empresa.razaoSocial : contraparte.nome,
      contraparte:
        tipo === "saida"
          ? contraparte
          : ({
              id: empresa.id,
              tipo: "pj",
              documento: empresa.cnpj,
              nome: empresa.razaoSocial,
            } satisfies Contraparte),
      itens: [item],
      totais,
      pagamento: {
        forma: i % 2 === 0 ? "pix" : "boleto",
        vencimento: new Date(data.getTime() + 14 * 24 * 60 * 60 * 1000)
          .toISOString()
          .slice(0, 10),
        parcelas: 1,
      },
      protocoloAutorizacao:
        status === "autorizada"
          ? `135${String(data.getFullYear()).slice(-2)}${String(data.getMonth() + 1).padStart(2, "0")}${String(numero).padStart(9, "0")}`
          : undefined,
      canceladaEm:
        status === "cancelada"
          ? new Date(data.getTime() + 2 * 24 * 60 * 60 * 1000).toISOString()
          : undefined,
      motivoCancelamento:
        status === "cancelada" ? "Erro na operação informada" : undefined,
      cartasCorrecao: [],
    };
    notas.push(nota);
  }
  return notas;
}

export function buscarContraparteMock(
  documento: string
): Contraparte | undefined {
  const limpo = documento.replace(/\D/g, "");
  return CONTRAPARTES_MOCK.find(
    (c) => c.documento.replace(/\D/g, "") === limpo
  );
}
