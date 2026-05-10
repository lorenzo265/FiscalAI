import { NextRequest, NextResponse } from "next/server";
import { mockLatency } from "@/lib/mocks/utils";
import { gerarEventosMesMock } from "@/lib/mocks/agenda";
import { lerContexto, contextoComoEmpresa } from "@/lib/mocks/contexto-empresa";
import {
  eventosAgendaSchema,
  type EventoAgenda,
} from "@/lib/schemas/agenda";

export async function GET(req: NextRequest) {
  await mockLatency();
  const ctx = lerContexto(req.nextUrl.searchParams);
  const empresa = contextoComoEmpresa(ctx);

  const params = req.nextUrl.searchParams;
  const modo = params.get("modo") ?? "mes";
  const ano = Number(params.get("ano") ?? new Date().getFullYear());
  const mes = Number(params.get("mes") ?? new Date().getMonth() + 1);

  let data: EventoAgenda[] = [];
  if (modo === "ano") {
    for (let m = 0; m < 12; m++) {
      const ref = new Date(ano, m, 15);
      data = data.concat(gerarEventosMesMock(empresa, ref));
    }
  } else {
    const ref = new Date(ano, mes - 1, 15);
    data = gerarEventosMesMock(empresa, ref);
  }

  const parsed = eventosAgendaSchema.safeParse(data);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_mock" }, { status: 500 });
  }
  return NextResponse.json(parsed.data);
}
