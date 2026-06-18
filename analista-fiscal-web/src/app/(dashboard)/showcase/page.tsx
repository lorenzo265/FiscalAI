"use client";

/**
 * Showcase do design-system Arkan (Fase 1).
 * Exibe TODAS as primitivas ui/* revestidas, os shared/*, a camada blueprint/*
 * e um exemplo de cada receita de motion (lib/motion/*). Página de referência da
 * frota — não é rota de produto. Caminho: /(dashboard)/_showcase
 */
import * as React from "react";
import { motion } from "framer-motion";
import {
  FileText,
  Inbox,
  Sparkles,
  ArrowRight,
  Bell,
  Search,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";

import { StatCard } from "@/components/shared/stat-card";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { MonoNumber } from "@/components/shared/mono-number";
import { DataBR } from "@/components/shared/data-br";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";

import {
  Framed,
  Fig,
  Ruler,
  RulerGauge,
  BlueprintSchematic,
  Carimbo,
} from "@/components/blueprint";
import { useCountUp } from "@/lib/motion/use-count-up";

import {
  reveal,
  revealChild,
  staggerChildren,
  lineMask,
  mediaFocus,
  defaultViewport,
} from "@/lib/motion/variants";
import { useReveal } from "@/lib/motion/use-reveal";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

/* ── Cabeçalho de seção numerado (FIG. 0X) ─────────────────────────────── */
function Secao({
  n,
  titulo,
  children,
}: {
  n: number;
  titulo: string;
  children: React.ReactNode;
}) {
  const r = useReveal();
  return (
    <motion.section {...r} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Fig n={n} titulo={titulo} />
        <Ruler />
      </div>
      {children}
    </motion.section>
  );
}

/* ── Número-herói demonstrando o hook useCountUp ───────────────────────── */
function NumeroHeroiDemo() {
  const n = useCountUp(847_320, { id: "showcase:hero" });
  return (
    <span className="mono text-5xl md:text-6xl font-light tabular-nums leading-none tracking-tight text-[var(--color-ink)]">
      <Moeda valor={n} />
    </span>
  );
}

export default function ShowcasePage() {
  const reduced = useReducedMotion();
  const [count, setCount] = React.useState(0);

  // Count-up (Receita E) — anima 0 → 92 ao montar.
  React.useEffect(() => {
    if (reduced) {
      setCount(92);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const dur = 1000;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      setCount(Math.round(eased * 92));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [reduced]);

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-14 pb-24">
        {/* ── Masthead / headline com line-mask (Receita C) ──────────── */}
        <header className="flex flex-col gap-6 pt-2">
          <div className="mono text-[11px] uppercase tracking-[0.2em] text-[var(--color-ink-3)]">
            Arkan · Design-system · Instrumento
          </div>
          <motion.h1
            variants={staggerChildren}
            initial="hidden"
            animate="show"
            className="font-[family-name:var(--font-serif)] text-5xl md:text-6xl font-semibold leading-[0.95] tracking-tight text-[var(--color-ink)] max-w-3xl"
          >
            {["Uma ferramenta de", "precisão, desenhada", "como um blueprint."].map(
              (linha) => (
                <span
                  key={linha}
                  className="block overflow-hidden"
                  style={{ paddingBottom: "0.06em" }}
                >
                  <motion.span
                    variants={reduced ? undefined : lineMask}
                    className="block"
                  >
                    {linha}
                  </motion.span>
                </span>
              )
            )}
          </motion.h1>
          <p className="max-w-xl text-[var(--color-ink-2)]">
            Papel quente, tinta e um único acento verde. Todas as primitivas,
            os componentes técnicos e as receitas de motion num só lugar.
          </p>
        </header>

        {/* ── 01 — Botões ────────────────────────────────────────────── */}
        <Secao n={1} titulo="Botões">
          <div className="flex flex-wrap items-center gap-3">
            <Button>
              Emitir nota <ArrowRight />
            </Button>
            <Button variant="secondary">Secundário</Button>
            <Button variant="outline">Contorno</Button>
            <Button variant="ghost">Fantasma</Button>
            <Button variant="destructive">Cancelar nota</Button>
            <Button variant="link">Ver detalhe</Button>
            <Button size="sm">Pequeno</Button>
            <Button size="lg">Grande</Button>
            <Button size="icon" aria-label="Buscar">
              <Search />
            </Button>
            <Button onClick={() => toast.success("Guia gerada", { description: "DAS 05/2026 pronta para download." })}>
              Disparar toast
            </Button>
          </div>
        </Secao>

        {/* ── 02 — Campos de formulário ──────────────────────────────── */}
        <Secao n={2} titulo="Formulário">
          <div className="grid gap-6 md:grid-cols-2 max-w-3xl">
            <div className="flex flex-col gap-2">
              <Label htmlFor="cnpj-demo">CNPJ</Label>
              <Input id="cnpj-demo" placeholder="00.000.000/0000-00" />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="regime-demo">Regime</Label>
              <Select>
                <SelectTrigger id="regime-demo">
                  <SelectValue placeholder="Selecione" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="simples">Simples Nacional</SelectItem>
                  <SelectItem value="presumido">Lucro Presumido</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-3">
              <Checkbox id="ck-demo" defaultChecked />
              <Label htmlFor="ck-demo" className="normal-case tracking-normal text-sm text-[var(--color-ink-2)]">
                Concordo com a apuração automática
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <Switch id="sw-demo" defaultChecked />
              <Label htmlFor="sw-demo" className="normal-case tracking-normal text-sm text-[var(--color-ink-2)]">
                Notificar por WhatsApp
              </Label>
            </div>
            <RadioGroup defaultValue="mensal" className="flex gap-6">
              <div className="flex items-center gap-2">
                <RadioGroupItem value="mensal" id="r1" />
                <Label htmlFor="r1" className="normal-case tracking-normal text-sm text-[var(--color-ink-2)]">
                  Mensal
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="anual" id="r2" />
                <Label htmlFor="r2" className="normal-case tracking-normal text-sm text-[var(--color-ink-2)]">
                  Anual
                </Label>
              </div>
            </RadioGroup>
          </div>
        </Secao>

        {/* ── 03 — Status: pills e badges ────────────────────────────── */}
        <Secao n={3} titulo="Status (cor + ícone + palavra)">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tom="ok">Conforme</Pill>
            <Pill tom="warn">Vence em 3d</Pill>
            <Pill tom="error">Rejeitada</Pill>
            <Pill tom="info">Em análise</Pill>
            <Pill tom="neutral">Rascunho</Pill>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Aprovada</Badge>
            <Badge variant="secondary">Lucro Presumido</Badge>
            <Badge variant="warn">Atenção</Badge>
            <Badge variant="destructive">Erro</Badge>
            <Badge variant="outline">Outline</Badge>
          </div>
        </Secao>

        {/* ── 04 — StatCards + dados em mono ──────────────────────────── */}
        <Secao n={4} titulo="Métricas">
          <motion.div
            variants={staggerChildren}
            initial="hidden"
            whileInView="show"
            viewport={defaultViewport}
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            {[
              { label: "Faturamento", valor: <Moeda valor={487230.55} />, pill: { tom: "ok" as const, texto: "+12%" } },
              { label: "DAS a pagar", valor: <Moeda valor={35612.4} />, sub: <>Vence em <DataBR value="2026-06-20" /></> },
              { label: "Notas no mês", valor: <MonoNumber>1.284</MonoNumber>, pill: { tom: "info" as const, texto: "Saída" } },
              { label: "Conformidade", valor: <MonoNumber>{count}%</MonoNumber>, sub: "Saúde fiscal" },
            ].map((s) => (
              <motion.div key={s.label} variants={reduced ? undefined : revealChild}>
                <StatCard {...s} />
              </motion.div>
            ))}
          </motion.div>
        </Secao>

        {/* ── 05 — Cards, tabs, accordion ────────────────────────────── */}
        <Secao n={5} titulo="Contêineres">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Resumo do regime</CardTitle>
                <CardDescription>
                  Lucro Presumido · apuração trimestral
                </CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-[var(--color-ink-2)]">
                Conteúdo enxuto, fio 1px, cantos quase retos — sem card
                flutuando com sombra suave.
              </CardContent>
            </Card>
            <Card interactive>
              <CardHeader>
                <CardTitle>Card interativo</CardTitle>
                <CardDescription>Hover sobe 1px + borda tinta</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-[var(--color-ink-2)]">
                Sem blur genérico; a elevação é a moldura.
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="guias" className="mt-2">
            <TabsList>
              <TabsTrigger value="guias">Guias</TabsTrigger>
              <TabsTrigger value="notas">Notas</TabsTrigger>
              <TabsTrigger value="razao">Razão</TabsTrigger>
            </TabsList>
            <TabsContent value="guias" className="text-sm text-[var(--color-ink-2)]">
              Tabs com sublinhado verde no ativo, rótulos em mono caixa-alta.
            </TabsContent>
            <TabsContent value="notas" className="text-sm text-[var(--color-ink-2)]">
              Conteúdo da aba Notas.
            </TabsContent>
            <TabsContent value="razao" className="text-sm text-[var(--color-ink-2)]">
              Conteúdo da aba Razão.
            </TabsContent>
          </Tabs>

          <Accordion type="single" collapsible className="max-w-xl">
            <AccordionItem value="a">
              <AccordionTrigger>Como a apuração é calculada?</AccordionTrigger>
              <AccordionContent>
                Pipeline determinístico Decimal-safe, com golden tests.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="b">
              <AccordionTrigger>Posso transmitir daqui?</AccordionTrigger>
              <AccordionContent>
                A transmissão é um ato consciente do cliente, com o certificado dele.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </Secao>

        {/* ── 06 — Alertas e progresso ───────────────────────────────── */}
        <Secao n={6} titulo="Feedback">
          <div className="flex flex-col gap-3 max-w-2xl">
            <Alert variant="ok">
              <Sparkles />
              <AlertTitle>Apuração conferida</AlertTitle>
              <AlertDescription>Todos os tributos batem com o esperado.</AlertDescription>
            </Alert>
            <Alert variant="warn">
              <Bell />
              <AlertTitle>Certidão vencendo</AlertTitle>
              <AlertDescription>A CND federal vence em 5 dias.</AlertDescription>
            </Alert>
            <Alert variant="destructive">
              <Bell />
              <AlertTitle>Nota rejeitada</AlertTitle>
              <AlertDescription>Rejeição 539: duplicidade de NF-e.</AlertDescription>
            </Alert>
          </div>
          <div className="flex flex-col gap-3 max-w-md mt-2">
            <Progress value={count} tom="green" />
            <Progress value={62} tom="ochre" />
            <Progress value={34} tom="danger" />
          </div>
        </Secao>

        {/* ── 07 — Overlays ──────────────────────────────────────────── */}
        <Secao n={7} titulo="Overlays">
          <div className="flex flex-wrap items-center gap-3">
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline">Abrir diálogo</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Confirmar emissão</DialogTitle>
                  <DialogDescription>
                    A nota será transmitida à SEFAZ com o certificado da empresa.
                  </DialogDescription>
                </DialogHeader>
                <div className="flex justify-end gap-2">
                  <Button variant="ghost">Cancelar</Button>
                  <Button>Emitir</Button>
                </div>
              </DialogContent>
            </Dialog>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost">Abrir popover</Button>
              </PopoverTrigger>
              <PopoverContent>
                <p className="text-sm text-[var(--color-ink-2)]">
                  Detalhe sob demanda, em painel emoldurado.
                </p>
              </PopoverContent>
            </Popover>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="secondary">Passar o mouse</Button>
              </TooltipTrigger>
              <TooltipContent>Dica em tinta sobre papel</TooltipContent>
            </Tooltip>
          </div>
        </Secao>

        {/* ── 08 — Blueprint (a personalidade técnica) ───────────────── */}
        <Secao n={8} titulo="Blueprint">
          <div className="grid gap-6 lg:grid-cols-[260px_1fr] items-start">
            <Framed surface="paper">
              <Fig n={9} titulo="Esquemático da nota" className="mb-3" />
              <BlueprintSchematic width={210} />
              <p className="mt-3 text-xs text-[var(--color-ink-2)]">
                Desenho linha-grafite que se desenha (draw-on) ao entrar no viewport.
              </p>
            </Framed>

            <div className="flex flex-col gap-6">
              <Framed>
                <div className="flex items-center justify-between gap-4">
                  <div className="flex flex-col gap-1">
                    <span className="mono text-[10px] uppercase tracking-[0.16em] text-[var(--color-ink-3)]">
                      Parecer
                    </span>
                    <span className="font-[family-name:var(--font-serif)] text-2xl text-[var(--color-ink)]">
                      Nota conferida
                    </span>
                    <span className="text-sm text-[var(--color-ink-2)]">
                      Painel <code className="mono">Framed</code> com crop marks nos cantos.
                    </span>
                  </div>
                  <Carimbo tom="green" sub="02/06/2026" inView>
                    Conforme
                  </Carimbo>
                </div>
              </Framed>

              <div className="flex flex-wrap items-center gap-6">
                <Carimbo tom="ink" sub="protocolo 4471">Registrado</Carimbo>
                <Carimbo tom="danger" sub="rej. 539">Rejeitada</Carimbo>
              </div>

              <div className="flex flex-col gap-2">
                <Fig n={10} titulo="Régua de medição" size="sm" />
                <Ruler />
                <Ruler majorEvery={4} gap={6} />
              </div>

              {/* Régua de limites (assinatura nº 2) — preenchimento + projeção */}
              <div className="flex flex-col gap-3">
                <Fig n={11} titulo="Régua de limites · RulerGauge" size="sm" />
                <Framed marks={false} surface="card">
                  <RulerGauge
                    label="Teto do Simples"
                    valor={2_640_000}
                    limite={3_600_000}
                    projecao={3_200_000}
                    projecaoLabel="no seu ritmo: outubro"
                    valorLabel="73% usado"
                  />
                </Framed>
              </div>
            </div>
          </div>
        </Secao>

        {/* ── 09 — Motion (receitas A–F) ─────────────────────────────── */}
        <Secao n={9} titulo="Motion">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Receita A — box reveal por wipe + filhos escalonados */}
            <motion.div
              variants={reveal}
              initial="hidden"
              whileInView="show"
              viewport={defaultViewport}
            >
              <Framed>
                <Fig n={11} titulo="Receita A — box wipe" size="sm" className="mb-3" />
                <motion.ul
                  variants={staggerChildren}
                  className="flex flex-col gap-2 text-sm text-[var(--color-ink-2)]"
                >
                  {["Corte clip-path de cima→baixo", "Filhos sobem escalonados", "Easing --ease-reveal"].map(
                    (t) => (
                      <motion.li key={t} variants={reduced ? undefined : revealChild}>
                        {t}
                      </motion.li>
                    )
                  )}
                </motion.ul>
              </Framed>
            </motion.div>

            {/* Receita B — un-blur + scale-into-focus */}
            <Framed>
              <Fig n={12} titulo="Receita B — un-blur" size="sm" className="mb-3" />
              <motion.div
                variants={mediaFocus}
                initial="hidden"
                whileInView="show"
                viewport={defaultViewport}
                className="grid h-28 place-items-center rounded-[var(--radius-sm)] border border-[var(--color-rule)] bg-[var(--color-paper-2)]"
              >
                <FileText className="size-8 text-[var(--color-graphite)]" />
              </motion.div>
            </Framed>
          </div>

          {/* Número-herói com useCountUp (v2 §4) — conta 1× por valor/sessão */}
          <Framed marks={false} surface="card" className="flex flex-col gap-1">
            <Fig n={13} titulo="Número-herói · useCountUp" size="sm" />
            <NumeroHeroiDemo />
            <span className="text-xs text-[var(--color-ink-2)]">
              Mono light, conta da base até o valor em 600ms ease-out — só na
              primeira vez por sessão.
            </span>
          </Framed>

          <p className="text-xs text-[var(--color-ink-2)] max-w-2xl">
            Receita C (line-mask) está no headline do topo · Receita D (draw-on)
            no esquemático da nota · Receita E (count-up) na métrica de
            Conformidade · Receita F (carimbo) nos selos acima. Tudo honra{" "}
            <code className="mono">prefers-reduced-motion</code>.
          </p>
        </Secao>

        {/* ── 10 — Estados (empty / loading / error) ─────────────────── */}
        <Secao n={10} titulo="Estados">
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <EmptyState
                titulo="Nenhuma nota ainda"
                descricao="As notas emitidas aparecem aqui."
                icone={Inbox}
                acao={<Button size="sm">Emitir primeira</Button>}
              />
            </Card>
            <Card>
              <LoadingState titulo="Apurando…" />
            </Card>
            <Card>
              <ErrorState onTentarNovamente={() => toast("Recarregando…")} />
            </Card>
          </div>
        </Secao>

        {/* ── Skeletons + separador ──────────────────────────────────── */}
        <section className="flex flex-col gap-4">
          <Fig n={11} titulo="Skeleton" />
          <Ruler />
          <div className="flex flex-col gap-2 max-w-md">
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
          <Separator className="my-4" />
          <p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--color-ink-3)]">
            Fim — Arkan design-system
          </p>
        </section>
      </div>
    </TooltipProvider>
  );
}
