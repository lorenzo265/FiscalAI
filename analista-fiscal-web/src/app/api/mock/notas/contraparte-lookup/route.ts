import { NextRequest, NextResponse } from "next/server";
import { mockLatency } from "@/lib/mocks/utils";
import { buscarContraparteMock } from "@/lib/mocks/notas";
import { contraparteSchema } from "@/lib/schemas/nota";

export async function POST(req: NextRequest) {
  await mockLatency(200, 600);
  let body: { documento?: string };
  try {
    body = (await req.json()) as { documento?: string };
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }
  const documento = (body.documento ?? "").replace(/\D/g, "");
  if (documento.length !== 11 && documento.length !== 14) {
    return NextResponse.json({ error: "documento_invalido" }, { status: 400 });
  }
  const contraparte = buscarContraparteMock(documento);
  if (!contraparte) {
    return NextResponse.json({ error: "nao_encontrado" }, { status: 404 });
  }
  const parsed = contraparteSchema.safeParse(contraparte);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_mock" }, { status: 500 });
  }
  return NextResponse.json(parsed.data);
}
