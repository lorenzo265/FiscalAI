import { NextRequest, NextResponse } from "next/server";
import { mockLatency } from "@/lib/mocks/utils";
import { gerarGuiasMock } from "@/lib/mocks/guias";
import { lerContexto, contextoComoEmpresa } from "@/lib/mocks/contexto-empresa";
import { guiasDASSchema } from "@/lib/schemas/guias";

export async function GET(req: NextRequest) {
  await mockLatency();
  const ctx = lerContexto(req.nextUrl.searchParams);
  const empresa = contextoComoEmpresa(ctx);
  const data = gerarGuiasMock(empresa);
  const parsed = guiasDASSchema.safeParse(data);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_mock" }, { status: 500 });
  }
  return NextResponse.json(parsed.data);
}
