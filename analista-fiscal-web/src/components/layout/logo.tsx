import { cn } from "@/lib/utils";

type Props = {
  size?: number;
  className?: string;
};

export function Logo({ size = 28, className }: Props) {
  return (
    <div
      className={cn(
        "relative grid place-items-center rounded-md overflow-hidden",
        className
      )}
      style={{
        width: size,
        height: size,
        background:
          "linear-gradient(135deg, var(--color-lime) 0%, var(--color-blue) 100%)",
      }}
    >
      <svg
        viewBox="0 0 24 24"
        width={size * 0.55}
        height={size * 0.55}
        fill="none"
        stroke="#06080f"
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polygon points="12 2 21 7 21 17 12 22 3 17 3 7 12 2" />
      </svg>
    </div>
  );
}
