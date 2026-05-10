import { formatarMoeda } from "@/lib/format/moeda";
import { cn } from "@/lib/utils";

type Props = {
  valor: number;
  className?: string;
};

export function Moeda({ valor, className }: Props) {
  return (
    <span className={cn("mono", className)}>{formatarMoeda(valor)}</span>
  );
}
