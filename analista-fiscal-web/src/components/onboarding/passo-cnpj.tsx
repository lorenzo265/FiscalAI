"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Search, CheckCircle2, Building2, MapPin, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pill } from "@/components/shared/pill";
import { validarCNPJ, apenasDigitos, formatarCNPJ } from "@/lib/format/cnpj";
import { api, ApiError } from "@/lib/api-client";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function PassoCnpj() {
  const cnpj = useOnboardingStore((s) => s.cnpj);
  const dados = useOnboardingStore((s) => s.dadosReceita);
  const setCnpj = useOnboardingStore((s) => s.setCnpj);
  const setDados = useOnboardingStore((s) => s.setDadosReceita);
  const setEmpresaCriada = useOnboardingStore((s) => s.setEmpresaCriada);
  const setRegime = useOnboardingStore((s) => s.setRegime);
  const setAnexoSimples = useOnboardingStore((s) => s.setAnexoSimples);
  const setFaturamento12m = useOnboardingStore((s) => s.setFaturamento12m);
  const proximo = useOnboardingStore((s) => s.proximo);
  const empresaCriada = useOnboardingStore((s) => s.empresaCriada);
  const reset = useOnboardingStore((s) => s.reset);

  const router = useRouter();
  const { salvarEmpresa, refresh } = useEmpresaAtual();

  const [erro, setErro] = React.useState<string | null>(null);
  const [carregando, setCarregando] = React.useState(false);
  const [entrando, setEntrando] = React.useState(false);

  // CNPJ-first (X15): a empresa já foi criada no backend pelo lookup, com regime/
  // anexo/faturamento inferidos. O dono pode ir DIRETO para o painel; certificado
  // e bancos são opcionais e configuráveis depois, em contexto. Reusa o mesmo
  // salvar+refresh+reset+/home da tela de conclusão (sem cert/bancos).
  async function irParaPainel() {
    if (!empresaCriada) return;
    setEntrando(true);
    try {
      await salvarEmpresa(empresaCriada);
      await refresh();
      reset();
      toast.success("Pronto — bem-vindo ao Arkan.");
      router.push("/home");
    } catch {
      toast.error("Não conseguimos abrir o painel agora. Tente de novo.");
      setEntrando(false);
    }
  }

  // Texto livre EXATAMENTE como o usuário digita (aceita `. / -`, espaços ou só
  // dígitos). NÃO reformatamos a cada tecla — era isso que jogava o cursor pro
  // fim e impedia apagar um caractere no meio. A máscara bonita entra só no blur.
  const [texto, setTexto] = React.useState<string>(() =>
    validarCNPJ(cnpj) ? formatarCNPJ(cnpj) : cnpj
  );

  const digitos = apenasDigitos(texto);
  const valido = validarCNPJ(digitos);

  function aoDigitarCnpj(e: React.ChangeEvent<HTMLInputElement>): void {
    // Permite dígitos + separadores comuns (. / - e espaço); descarta o resto.
    // Limita a 18 chars (14 dígitos + 4 separadores de "00.000.000/0000-00").
    const limpo = e.target.value.replace(/[^\d./\-\s]/g, "").slice(0, 18);
    setTexto(limpo);
    setCnpj(apenasDigitos(limpo));
    setErro(null);
    setDados(null);
  }

  async function buscar() {
    if (!valido) {
      setErro("CNPJ inválido. Confira os 14 dígitos.");
      return;
    }
    setErro(null);
    setCarregando(true);
    try {
      // O onboarding do backend consulta a Receita (BrasilAPI) E já cria a
      // empresa no tenant — capturamos ambos. Enviamos sempre SÓ os dígitos.
      const { dados: r, empresa } = await api.empresa.lookupCnpjComEmpresa(
        digitos
      );
      setDados(r);
      setEmpresaCriada(empresa);
      // Pré-preenche regime/anexo/faturamento com o que o backend derivou,
      // para os passos seguintes refletirem a sugestão (o usuário pode ajustar).
      if (empresa) {
        setRegime(empresa.regime);
        if (empresa.anexoSimples) setAnexoSimples(empresa.anexoSimples);
        if (empresa.faturamento12m > 0)
          setFaturamento12m(empresa.faturamento12m);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setErro("Não conseguimos consultar este CNPJ agora. Tente novamente.");
      } else {
        setErro("Erro inesperado.");
      }
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Label
          htmlFor="cnpj"
          className="text-[11px] mono uppercase tracking-[0.12em] font-bold text-[var(--color-ink-3)]"
        >
          CNPJ da empresa
        </Label>
        <div className="flex gap-2">
          <Input
            id="cnpj"
            inputMode="text"
            placeholder="00.000.000/0000-00"
            className="mono text-base"
            style={{ fontVariantNumeric: "tabular-nums" }}
            value={texto}
            onChange={aoDigitarCnpj}
            onBlur={() => {
              // Formata bonito só quando o CNPJ está completo e válido — sem
              // atrapalhar a edição no meio enquanto o usuário ainda digita.
              if (validarCNPJ(digitos)) setTexto(formatarCNPJ(digitos));
            }}
            aria-invalid={texto.length > 0 && !valido}
          />
          <Button onClick={buscar} disabled={!valido || carregando}>
            <Search className="size-4" />
            {carregando ? "Buscando..." : "Buscar"}
          </Button>
        </div>
        {erro ? (
          <p className="text-xs text-[var(--color-danger)]">{erro}</p>
        ) : null}
        <p className="text-[11px] text-[var(--color-ink-3)]">
          O CNPJ é consultado na Receita Federal. Não armazenamos dados fora
          deste navegador nesta demonstração.
        </p>
      </div>

      {/* resultado encontrado */}
      {dados ? (
        <div
          className="rounded-[var(--radius-md)] border flex flex-col gap-4 overflow-hidden"
          style={{
            background: "var(--color-green-wash)",
            borderColor: "var(--color-green)",
          }}
        >
          <div className="px-5 pt-4 pb-2 flex items-start gap-3">
            <div
              className="size-9 rounded-[var(--radius-sm)] grid place-items-center mt-0.5 border shrink-0"
              style={{
                background: "var(--color-green-wash)",
                borderColor: "var(--color-green)",
              }}
            >
              <CheckCircle2
                className="size-5"
                style={{ color: "var(--color-green)" }}
              />
            </div>
            <div className="flex-1">
              <p className="text-[11px] uppercase tracking-[0.14em] font-bold mono"
                 style={{ color: "var(--color-green)" }}>
                empresa encontrada
              </p>
              <h3 className="font-serif text-lg text-[var(--color-ink)] mt-1">
                {dados.razaoSocial}
              </h3>
              <p className="mono text-xs text-[var(--color-ink-2)] mt-0.5"
                 style={{ fontVariantNumeric: "tabular-nums" }}>
                <abbr title="Cadastro Nacional de Pessoas Jurídicas">{formatarCNPJ(dados.cnpj)}</abbr> · {dados.porte}
              </p>
            </div>
            <Pill tom="ok">{dados.situacao}</Pill>
          </div>

          <div className="border-t" style={{ borderColor: "var(--color-green)" }} />

          <dl className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm px-5 pb-2">
            <ItemDl icone={<Building2 className="size-3.5" />} label="Atividade principal">
              <span className="text-[var(--color-ink)]">{dados.cnaePrincipal.descricao}</span>
            </ItemDl>
            <ItemDl icone={<MapPin className="size-3.5" />} label="Endereço">
              <span className="text-[var(--color-ink)]">
                {dados.endereco.logradouro}, {dados.endereco.numero} ·{" "}
                {dados.endereco.municipio}/{dados.endereco.uf}
              </span>
            </ItemDl>
          </dl>

          <div className="flex flex-col gap-3 px-5 pb-5">
            <p className="text-[11px] text-[var(--color-ink-2)] leading-relaxed">
              Já dá pra começar. Certificado digital e contas bancárias você
              conecta depois, direto no painel — quando precisar.
            </p>
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
              <Button variant="outline" onClick={proximo}>
                Revisar e configurar agora
              </Button>
              <Button onClick={irParaPainel} disabled={entrando || !empresaCriada}>
                {entrando ? "Abrindo..." : "Ir para o painel"}
                <ArrowRight className="size-4" />
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ItemDl({
  icone,
  label,
  children,
}: {
  icone: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-ink-3)]">
        {icone}
        {label}
      </span>
      {children}
    </div>
  );
}
