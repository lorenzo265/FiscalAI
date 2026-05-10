import { NextRequest, NextResponse } from "next/server";
import { mockLatency } from "@/lib/mocks/utils";
import { gerarHistoricoMock } from "@/lib/mocks/fiscal";
import { lerContexto, contextoComoEmpresa } from "@/lib/mocks/contexto-empresa";
import { historicoFiscalSchema } from "@/lib/schemas/fiscal";

export async function GET(req: NextRequest) {
  await mockLatency();
  const ctx = lerContexto(req.nextUrl.searchParams);
  const meses = Number(req.nextUrl.searchParams.get("meses") ?? "6");
  const empresa = contextoComoEmpresa(ctx);
  const data = gerarHistoricoMock(empresa, Math.max(1, Math.min(24, meses)));
  const parsed = historicoFiscalSchema.safeParse(data);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_mock" }, { status: 500 });
  }
  return NextResponse.json(parsed.data);
}
