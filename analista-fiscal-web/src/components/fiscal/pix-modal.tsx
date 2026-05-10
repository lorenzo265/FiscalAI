"use client";

import * as React from "react";
import QRCode from "qrcode";
import { Check, Copy, QrCode as QrIcon } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Moeda } from "@/components/shared/moeda";
import { formatarDataBR } from "@/lib/format/data";

type Props = {
  aberto: boolean;
  onAbertoChange: (v: boolean) => void;
  valor: number;
  vencimento: string;
  pixCopiaCola: string;
  rotuloPeriodo: string;
};

export function PixModal({
  aberto,
  onAbertoChange,
  valor,
  vencimento,
  pixCopiaCola,
  rotuloPeriodo,
}: Props) {
  const [qrUrl, setQrUrl] = React.useState<string>("");
  const [copiado, setCopiado] = React.useState(false);

  React.useEffect(() => {
    if (!aberto) return;
    let cancelado = false;
    QRCode.toDataURL(pixCopiaCola, {
      width: 240,
      margin: 1,
      color: { dark: "#06080f", light: "#ffffff" },
    })
      .then((url) => {
        if (!cancelado) setQrUrl(url);
      })
      .catch(() => {
        if (!cancelado) setQrUrl("");
      });
    return () => {
      cancelado = true;
    };
  }, [aberto, pixCopiaCola]);

  const copiar = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(pixCopiaCola);
      setCopiado(true);
      toast.success("PIX copiado", {
        description: "Cole no app do seu banco pra concluir o pagamento.",
      });
      window.setTimeout(() => setCopiado(false), 2500);
    } catch {
      toast.error("Não consegui copiar", {
        description: "Tente selecionar e copiar manualmente.",
      });
    }
  }, [pixCopiaCola]);

  return (
    <Dialog open={aberto} onOpenChange={onAbertoChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <QrIcon className="size-4 text-[var(--color-lime)]" />
            Pagar via PIX
          </DialogTitle>
          <DialogDescription>
            DAS de {rotuloPeriodo} · vence em {formatarDataBR(vencimento)}
          </DialogDescription>
        </DialogHeader>

        <div
          className="rounded-md border p-4 flex flex-col items-center gap-3"
          style={{
            background: "var(--color-card-2)",
            borderColor: "var(--color-line-2)",
          }}
        >
          {qrUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={qrUrl}
              alt="QR Code PIX"
              className="size-[200px] rounded-md bg-white p-2"
            />
          ) : (
            <div className="size-[200px] rounded-md bg-[var(--color-card-3)] animate-pulse" />
          )}
          <span className="mono text-2xl font-bold text-[var(--color-txt)]">
            <Moeda valor={valor} />
          </span>
          <span className="text-[11px] text-[var(--color-txt-3)]">
            Aponte a câmera do app do seu banco
          </span>
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)]">
            PIX copia e cola
          </span>
          <div
            className="rounded-md border px-3 py-2 mono text-[11px] text-[var(--color-txt-2)] break-all leading-relaxed max-h-24 overflow-auto"
            style={{
              background: "var(--color-card-2)",
              borderColor: "var(--color-line-2)",
            }}
          >
            {pixCopiaCola}
          </div>
          <Button onClick={copiar} variant={copiado ? "secondary" : "default"}>
            {copiado ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            {copiado ? "Copiado" : "Copiar PIX"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
