"use client";

import * as React from "react";
import { motion, type Variants } from "framer-motion";
import { Gauge, TrendingUp } from "lucide-react";
import { Framed } from "@/components/blueprint/framed";
import { Carimbo } from "@/components/blueprint/carimbo";
import { RulerGauge } from "@/components/blueprint/ruler";
import { Moeda } from "@/components/shared/moeda";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { useCountUp } from "@/lib/motion/use-count-up";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { formatarMoeda } from "@/lib/format/moeda";
import { FATOR_R, ANEXOS } from "@/lib/traducao/obrigacoes";

/* ─────────────────────────────────────────────────────────────────────────────
 * Constantes de limite
 * ──────────────────────────────────────────────────────────────────────────── */
const LIMITE_MEI = 81_000;

/* ─────────────────────────────────────────────────────────────────────────────
 * projetarMesCruzamento — lógica pura idêntica à do simples-nacional-card.
 * Duplicada aqui (NÃO importada da home) para evitar acoplamento entre telas.
 * Qualquer mudança de comportamento deve ser feita nos dois lugares ou extraída
 * para src/lib/fiscal/projetar-cruzamento.ts num refactor futuro.
 * ──────────────────────────────────────────────────────────────────────────── */
function projetarMesCruzamento(
  fatAtual: number,
  limite: number,
  mesAtual: number /* 0–11 */
): { valor: number; label: string } | null {
  if (fatAtual <= 0 || fatAtual >= limite) return null;
  const mesesDecorridos = mesAtual + 1;
  const ritmoMensal = fatAtual / mesesDecorridos;
  if (ritmoMensal <= 0) return null;
  const mesesParaCruzar = Math.ceil((limite - fatAtual) / ritmoMensal);
  const mesCruzamento = mesAtual + mesesParaCruzar;
  if (mesCruzamento > 11) return null; // não cruza no ano corrente
  const valorProjetado = fatAtual + ritmoMensal * mesesParaCruzar;
  const label = new Intl.DateTimeFormat("pt-BR", { month: "short" }).format(
    new Date(new Date().getFullYear(), mesCruzamento, 1)
  );
  return { valor: valorProjetado, label: `no ritmo: ${label}` };
}

/* ─────────────────────────────────────────────────────────────────────────────
 * Página principal
 * ──────────────────────────────────────────────────────────────────────────── */
export default function FiscalLimitesPage() {
  const { empresa } = useEmpresaAtual();
  const apuracao = useApuracaoAtual();
  const reduced = useReducedMotion();

  const containerVariants: Variants = reduced ? staticVariants : staggerChildren;
  const itemVariants: Variants = reduced ? staticVariants : revealChild;
  const pageReveal: Variants = reduced ? staticVariants : reveal;

  const regime = empresa?.regime;

  /* ── número-herói: faturamento acumulado 12m ── */
  const fat12 = apuracao.data?.faturamento12m ?? empresa?.faturamento12m ?? 0;
  const fat12Centavos = Math.round(fat12 * 100);
  const heroRaw = useCountUp(fat12Centavos, {
    id: "limites:faturamento12m",
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);

  /* ── limites e projeções ── */
  const mesAtual = new Date().getMonth();

  const sublimite = apuracao.data?.sublimiteEstadual ?? 3_600_000;
  const teto = apuracao.data?.tetoSimples ?? 4_800_000;

  const projMei = projetarMesCruzamento(fat12, LIMITE_MEI, mesAtual);
  const projSub = projetarMesCruzamento(fat12, sublimite, mesAtual);
  const projTeto = projetarMesCruzamento(fat12, teto, mesAtual);

  const pctMei = Math.min(100, Math.round((fat12 / LIMITE_MEI) * 100));
  const pctSub = Math.min(100, Math.round((fat12 / sublimite) * 100));
  const pctTeto = Math.min(100, Math.round((fat12 / teto) * 100));

  /* ── Fator R ── */
  const fatorR = apuracao.data?.fatorR;

  /* ── estado geral (para Carimbo "Dentro do limite") ── */
  const tudoFolgado = (() => {
    if (regime === "MEI") return pctMei < 80;
    if (regime === "SIMPLES_NACIONAL") return pctSub < 80 && pctTeto < 80;
    return false;
  })();

  /* ── contexto da linha herói ("X% do teto") ── */
  const percentualDoTeto = regime === "MEI"
    ? pctMei
    : regime === "SIMPLES_NACIONAL"
      ? pctTeto
      : 0;
  const limitePrincipal = regime === "MEI" ? LIMITE_MEI : teto;
  const tituloPagina = regime === "MEI" ? "Limite do MEI" : "Limites do Simples";

  /* ── loading / error ── */
  if (apuracao.isLoading) {
    return (
      <PageShell
        pageReveal={pageReveal}
        containerVariants={containerVariants}
        itemVariants={itemVariants}
        heroFormatado={heroFormatado}
        titulo={tituloPagina}
        heroLoading
      >
        <LoadingState titulo="Calculando limites..." />
      </PageShell>
    );
  }

  if (apuracao.isError) {
    return (
      <PageShell
        pageReveal={pageReveal}
        containerVariants={containerVariants}
        itemVariants={itemVariants}
        heroFormatado={heroFormatado}
        titulo={tituloPagina}
      >
        <ErrorState onTentarNovamente={() => void apuracao.refetch()} />
      </PageShell>
    );
  }

  /* ── regime sem monitores de limite ── */
  if (regime !== "MEI" && regime !== "SIMPLES_NACIONAL") {
    return (
      <PageShell
        pageReveal={pageReveal}
        containerVariants={containerVariants}
        itemVariants={itemVariants}
        heroFormatado={heroFormatado}
        titulo={tituloPagina}
      >
        <EmptyState
          titulo="Monitores de limite não se aplicam"
          descricao="Os limites de faturamento são específicos do Simples Nacional e do MEI. No Lucro Presumido ou Lucro Real não há teto de regime."
          icone={Gauge}
        />
      </PageShell>
    );
  }

  return (
    <PageShell
      pageReveal={pageReveal}
      containerVariants={containerVariants}
      itemVariants={itemVariants}
      heroFormatado={heroFormatado}
      titulo={tituloPagina}
      percentualDoTeto={percentualDoTeto}
      limitePrincipal={limitePrincipal}
    >
      {/* ── Bloco 2: réguas de limite ── */}
      <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-5">
        {/* label de seção — Hanken, sem Fig. */}
        <div className="flex items-center justify-between gap-2 -mb-1">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-[var(--color-green)]" aria-hidden />
            <span className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
              {regime === "MEI" ? "Limite do MEI" : "Limites do Simples Nacional"}
            </span>
          </div>
          {tudoFolgado ? (
            <Carimbo tom="green" inView>Dentro do limite</Carimbo>
          ) : null}
        </div>

        {/* ── MEI: régua única ── */}
        {regime === "MEI" ? (
          <>
            <RulerGauge
              valor={fat12}
              limite={LIMITE_MEI}
              projecao={projMei?.valor}
              projecaoLabel={projMei?.label}
              label="Limite anual do MEI"
              valorLabel={
                <span className="mono tabular-nums text-[11px]">
                  <Moeda valor={fat12} /> / <Moeda valor={LIMITE_MEI} />
                  <span className="ml-2 text-[var(--color-ink-2)]">({pctMei}%)</span>
                </span>
              }
            />
            <AvisoDesenquadramento
              pct={pctMei}
              projecaoLabel={projMei?.label ?? null}
              tipo="mei"
              limite={LIMITE_MEI}
              fatAtual={fat12}
            />
          </>
        ) : (
          /* ── SIMPLES NACIONAL: duas réguas ── */
          <>
            <RulerGauge
              valor={fat12}
              limite={sublimite}
              projecao={projSub?.valor}
              projecaoLabel={projSub?.label}
              label="Sublimite estadual"
              valorLabel={
                <span className="mono tabular-nums text-[11px]">
                  <Moeda valor={fat12} /> / <Moeda valor={sublimite} />
                  <span className="ml-2 text-[var(--color-ink-2)]">({pctSub}%)</span>
                </span>
              }
            />
            <AvisoDesenquadramento
              pct={pctSub}
              projecaoLabel={projSub?.label ?? null}
              tipo="sublimite"
              limite={sublimite}
              fatAtual={fat12}
            />

            <div
              className="h-px w-full"
              style={{ background: "var(--color-rule)" }}
              aria-hidden
            />

            <RulerGauge
              valor={fat12}
              limite={teto}
              projecao={projTeto?.valor}
              projecaoLabel={projTeto?.label}
              label="Teto do Simples"
              valorLabel={
                <span className="mono tabular-nums text-[11px]">
                  <Moeda valor={fat12} /> / <Moeda valor={teto} />
                  <span className="ml-2 text-[var(--color-ink-2)]">({pctTeto}%)</span>
                </span>
              }
            />
            <AvisoDesenquadramento
              pct={pctTeto}
              projecaoLabel={projTeto?.label ?? null}
              tipo="teto"
              limite={teto}
              fatAtual={fat12}
            />
          </>
        )}
      </Framed>

      {/* ── Bloco 3: Fator R (condicional — só Simples c/ serviços) ── */}
      {fatorR && regime === "SIMPLES_NACIONAL" ? (
        <FatorRMonitor
          valor={fatorR.valor}
          anexo={fatorR.anexoAtual}
          atencao={fatorR.atencao}
        />
      ) : null}
    </PageShell>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
 * PageShell — estrutura fixa da tela (header + herói + subnav)
 * ──────────────────────────────────────────────────────────────────────────── */
function PageShell({
  children,
  pageReveal,
  containerVariants,
  itemVariants,
  heroFormatado,
  titulo,
  heroLoading,
  percentualDoTeto,
  limitePrincipal,
}: {
  children: React.ReactNode;
  pageReveal: Variants;
  containerVariants: Variants;
  itemVariants: Variants;
  heroFormatado: string;
  titulo: string;
  heroLoading?: boolean;
  percentualDoTeto?: number;
  limitePrincipal?: number;
}) {
  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageReveal}
      initial="hidden"
      animate="show"
    >
      {/* ── Bloco 1: cabeçalho + número-herói ── */}
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-4"
      >
        <div>
          <motion.span
            variants={itemVariants}
            className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
          >
            Módulo · Fiscal
          </motion.span>
          <motion.h1
            variants={itemVariants}
            className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
          >
            {titulo}
          </motion.h1>
        </div>

        {/* número-herói: faturamento acumulado 12m */}
        <motion.div variants={itemVariants} className="flex flex-col gap-1">
          {heroLoading ? (
            <div className="flex flex-col gap-2">
              <div
                className="h-14 w-52 rounded-[var(--radius-sm)] animate-pulse"
                style={{ background: "var(--color-paper-2)" }}
              />
              <div
                className="h-4 w-48 rounded-[var(--radius-sm)] animate-pulse"
                style={{ background: "var(--color-paper-2)" }}
              />
            </div>
          ) : (
            <>
              <span
                className="mono leading-none text-[var(--color-ink)] whitespace-nowrap"
                style={{
                  fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
                  fontWeight: 300,
                  fontVariantNumeric: "tabular-nums",
                  letterSpacing: "-0.02em",
                }}
                aria-label={`Faturamento acumulado nos últimos 12 meses: ${heroFormatado}`}
              >
                {heroFormatado}
              </span>
              <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
                faturado nos últimos 12 meses
                {percentualDoTeto != null && limitePrincipal != null ? (
                  <>
                    {" · "}
                    <span
                      className="mono font-semibold"
                      style={{
                        color:
                          percentualDoTeto >= 90
                            ? "var(--color-danger)"
                            : percentualDoTeto >= 70
                              ? "var(--color-ochre)"
                              : "var(--color-ink)",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {percentualDoTeto}%
                    </span>
                    {" do teto de "}
                    <span
                      className="mono font-semibold text-[var(--color-ink)]"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      <Moeda valor={limitePrincipal} />
                    </span>
                  </>
                ) : null}
              </span>
            </>
          )}
        </motion.div>
      </motion.header>

      <FiscalSubnav />

      {children}
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
 * AvisoDesenquadramento — aviso contextual traduzido para o dono de PME.
 * Só aparece quando pct >= 80 (atenção) ou quando há projeção de cruzamento.
 * ──────────────────────────────────────────────────────────────────────────── */
type TipoLimite = "mei" | "sublimite" | "teto";

const AVISOS: Record<
  TipoLimite,
  { aviso: string; cruzamento: string; estouro: string }
> = {
  mei: {
    aviso:
      "Você está se aproximando do teto do MEI (R$ 81 mil anuais). Acima desse valor, sua empresa precisa migrar para Microempresa (ME) no Simples Nacional.",
    cruzamento:
      "No seu ritmo atual, você ultrapassa o teto do MEI ainda neste ano. Converse com seu contador sobre a transição para ME.",
    estouro:
      "Você ultrapassou o limite anual do MEI. É necessário solicitar o desenquadramento e migrar para Microempresa (ME) no Simples Nacional.",
  },
  sublimite: {
    aviso:
      "Você está se aproximando do sublimite estadual (R$ 3,6 milhões). Acima desse valor, o ICMS (imposto estadual sobre vendas) e o ISS (imposto municipal sobre serviços) saem do DAS e passam a ser recolhidos separadamente para o estado e o município.",
    cruzamento:
      "No seu ritmo atual, você ultrapassa o sublimite estadual ainda neste ano. A partir desse ponto, ICMS e ISS serão cobrados à parte — o que pode aumentar sua carga tributária.",
    estouro:
      "Você ultrapassou o sublimite estadual. O ICMS e o ISS agora precisam ser recolhidos diretamente ao estado e ao município, fora do DAS. Fale com seu contador.",
  },
  teto: {
    aviso:
      "Você está se aproximando do teto do Simples Nacional (R$ 4,8 milhões). Acima desse valor, sua empresa é excluída do Simples e precisa migrar para o Lucro Presumido ou Lucro Real.",
    cruzamento:
      "No seu ritmo atual, você ultrapassa o teto do Simples Nacional ainda neste ano. Planeje com seu contador a migração de regime.",
    estouro:
      "Você ultrapassou o teto do Simples Nacional. Sua empresa precisa migrar para o Lucro Presumido ou Lucro Real. Entre em contato com seu contador com urgência.",
  },
};

function AvisoDesenquadramento({
  pct,
  projecaoLabel,
  tipo,
  limite,
  fatAtual,
}: {
  pct: number;
  projecaoLabel: string | null;
  tipo: TipoLimite;
  limite: number;
  fatAtual: number;
}) {
  const avisos = AVISOS[tipo];
  if (pct < 80 && !projecaoLabel) return null;

  const estouro = pct >= 100;
  const pillTom = estouro ? "error" : pct >= 90 ? "error" : "warn";
  const texto = estouro
    ? avisos.estouro
    : projecaoLabel
      ? avisos.cruzamento
      : avisos.aviso;

  const rotulo = estouro
    ? "Limite ultrapassado"
    : projecaoLabel
      ? `Projeção de cruzamento — ${projecaoLabel}`
      : "Atenção";

  return (
    <div
      className="flex flex-col gap-1.5 rounded-[var(--radius-sm)] border p-3"
      style={{
        background: estouro
          ? "var(--color-danger-wash)"
          : "var(--color-ochre-wash)",
        borderColor: estouro
          ? "var(--color-danger)"
          : "var(--color-ochre)",
      }}
    >
      <div className="flex items-center gap-2">
        <Pill tom={pillTom}>{rotulo}</Pill>
        {!estouro && pct > 0 ? (
          <span className="mono text-[10px] font-semibold tabular-nums"
            style={{ color: "var(--color-ochre)" }}>
            faltam{" "}
            <Moeda valor={Math.max(0, limite - fatAtual)} />
          </span>
        ) : null}
      </div>
      <p
        className="text-[12px] leading-relaxed"
        style={{
          color: estouro ? "var(--color-danger)" : "var(--color-ochre)",
        }}
      >
        {texto}
      </p>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
 * FatorRMonitor — Medidor do Fator R com a RulerGauge
 * Mostra a proporção folha÷receita vs. o umbral de 28%, com tradução do efeito.
 * ──────────────────────────────────────────────────────────────────────────── */
function FatorRMonitor({
  valor,
  anexo,
  atencao,
}: {
  valor: number;
  anexo: "III" | "V";
  atencao: boolean;
}) {
  const pct = (valor * 100).toFixed(1).replace(".", ",");
  const anexoTraduzido = ANEXOS[anexo];
  /* O Fator R é medido em relação a 28% (umbral). Mostramos a régua de 0 a 40%
   * para dar contexto visual sem distorcer (os extremos reais ficam em ~0–50%). */
  const ESCALA_MAX = 0.4;

  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-4">
      {/* label de seção */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-[var(--color-ink-2)]" aria-hidden />
          <span className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
            {FATOR_R.titulo}
            {" "}
            <abbr
              title={FATOR_R.termoTecnico}
              className="mono text-[10px] font-normal text-[var(--color-ink-3)] no-underline"
            >
              ({FATOR_R.termoTecnico})
            </abbr>
          </span>
        </div>
        <Pill tom={atencao ? "warn" : "ok"}>
          {atencao
            ? "abaixo de 28% — alíquota maior"
            : `${anexoTraduzido.titulo} mantido`}
        </Pill>
      </div>

      {/* valor destacado */}
      <div className="flex items-baseline gap-2">
        <span
          className="mono font-bold text-[var(--color-ink)] leading-none"
          style={{
            fontSize: 28,
            fontVariantNumeric: "tabular-nums",
            color: atencao ? "var(--color-ochre)" : "var(--color-ink)",
          }}
        >
          {pct}%
        </span>
        <span className="text-[12px] text-[var(--color-ink-2)]">
          folha ÷ receita dos últimos 12 meses
        </span>
      </div>

      {/* régua Fator R vs. umbral 28% */}
      <RulerGauge
        valor={Math.min(valor, ESCALA_MAX)}
        limite={ESCALA_MAX}
        projecao={0.28}
        projecaoLabel="umbral 28%"
        label="Folha como % do faturamento"
        valorLabel={
          <span className="mono tabular-nums text-[11px]">
            <span style={{ color: atencao ? "var(--color-ochre)" : "var(--color-ink)" }}>
              {pct}%
            </span>
            {" / "}
            <span className="text-[var(--color-ink-2)]">28% = umbral</span>
          </span>
        }
        ticks={8}
      />

      {/* explicação do efeito — em PT claro, sem jargão */}
      <div
        className="rounded-[var(--radius-sm)] border p-3 text-[12px] leading-relaxed"
        style={{
          background: atencao ? "var(--color-ochre-wash)" : "var(--color-green-wash)",
          borderColor: atencao ? "var(--color-ochre)" : "var(--color-green)",
          color: atencao ? "var(--color-ochre)" : "var(--color-green-deep)",
        }}
      >
        {atencao ? (
          <>
            <strong>Sua folha representa {pct}% do faturamento — abaixo de 28%.</strong>
            {" "}Isso significa que você está no{" "}
            <abbr title={`Anexo ${anexo} do Simples Nacional`} className="no-underline">
              {anexoTraduzido.titulo} ({ANEXOS[anexo].termoTecnico})
            </abbr>
            {", que tem alíquota maior. "}
            Aumentar a folha de pagamento acima de 28% do faturamento migra você para
            o{" "}
            <abbr title="Anexo III do Simples Nacional" className="no-underline">
              {ANEXOS["III"].titulo} ({ANEXOS["III"].termoTecnico})
            </abbr>
            , com alíquota menor.
          </>
        ) : (
          <>
            <strong>Sua folha representa {pct}% do faturamento — acima de 28%.</strong>
            {" "}Você está no{" "}
            <abbr title={`Anexo ${anexo} do Simples Nacional`} className="no-underline">
              {anexoTraduzido.titulo} ({ANEXOS[anexo].termoTecnico})
            </abbr>
            {", com a alíquota mais favorável para prestadores de serviço. "}
            Mantenha sua folha acima de 28% do faturamento para conservar essa vantagem.
          </>
        )}
      </div>
    </Framed>
  );
}
