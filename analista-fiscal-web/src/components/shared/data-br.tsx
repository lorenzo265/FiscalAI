import { formatarDataBR, formatarDataHoraBR } from "@/lib/format/data";
import { cn } from "@/lib/utils";

type Props = {
  value: Date | string | number;
  comHora?: boolean;
  className?: string;
};

export function DataBR({ value, comHora, className }: Props) {
  const text = comHora ? formatarDataHoraBR(value) : formatarDataBR(value);
  return <span className={cn("mono", className)}>{text}</span>;
}
