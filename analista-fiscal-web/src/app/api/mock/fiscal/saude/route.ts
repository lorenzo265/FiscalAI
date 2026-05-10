import { NextRequest, NextResponse } from "next/server";
import { mockLatency } from "@/lib/mocks/utils";
import { gerarFiscalHealthMock } from "@/lib/mocks/fiscal";
import { lerContexto, contextoComoEmpresa } from "@/lib/mocks/contexto-empresa";
import { fiscalHealthSchema } from "@/lib/schemas/fiscal";

export async function GET(req: NextRequest) {
  await mockLatency();
  const ctx = lerContexto(req.nextUrl.searchParams);
  const empresa = contextoComoEmpresa(ctx);
  const data = gerarFiscalHealthMock(empresa);
  const parsed = fiscalHealthSchema.safeParse(data);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_mock" }, { status: 500 });
  }
  return NextResponse.json(parsed.data);
}
