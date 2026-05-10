import { NextResponse } from "next/server";
import { mockLatency } from "@/lib/mocks/utils";
import { CATALOGO_PRODUTOS } from "@/lib/mocks/seeds/catalogo-produtos";

export async function GET() {
  await mockLatency();
  return NextResponse.json(CATALOGO_PRODUTOS);
}
