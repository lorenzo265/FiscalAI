import { cn } from "@/lib/utils";

type Props = {
  children: React.ReactNode;
  className?: string;
};

export function MonoNumber({ children, className }: Props) {
  return <span className={cn("mono", className)}>{children}</span>;
}
