import { NextRequest, NextResponse } from "next/server";
import { mockLatency } from "@/lib/mocks/utils";
import { gerarCnpjLookupMock } from "@/lib/mocks/empresa";
import { apenasDigitos, validarCNPJ } from "@/lib/format/cnpj";
import { cnpjLookupResponseSchema } from "@/lib/schemas/cnpj-lookup";

export async function POST(req: NextRequest) {
  await mockLatency(900, 1400);

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const cnpj = (body as { cnpj?: string })?.cnpj ?? "";
  const digits = apenasDigitos(cnpj);

  if (digits.length !== 14) {
    return NextResponse.json(
      { error: "cnpj_invalid_length" },
      { status: 400 }
    );
  }

  if (!validarCNPJ(digits)) {
    return NextResponse.json(
      { error: "cnpj_invalid_check_digits" },
      { status: 400 }
    );
  }

  const data = gerarCnpjLookupMock(digits);
  const parsed = cnpjLookupResponseSchema.safeParse(data);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_mock" }, { status: 500 });
  }
  return NextResponse.json(parsed.data);
}
