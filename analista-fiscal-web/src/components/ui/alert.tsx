import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-[var(--radius-md)] border p-4 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:size-4 [&>svg~*]:pl-7",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-card)] border-[var(--color-rule)] text-[var(--color-ink)] [&>svg]:text-[var(--color-ink-2)]",
        info: "bg-[var(--color-paper-2)] border-[var(--color-rule-2)] text-[var(--color-ink)] [&>svg]:text-[var(--color-ink-2)]",
        warn: "bg-[var(--color-paper-2)] border-[var(--color-ochre)]/35 text-[var(--color-ink)] [&>svg]:text-[var(--color-ochre)]",
        destructive:
          "bg-[var(--color-paper-2)] border-[var(--color-danger)]/40 text-[var(--color-ink)] [&>svg]:text-[var(--color-danger)]",
        ok: "bg-[var(--color-green-wash)] border-[var(--color-green)]/35 text-[var(--color-green-deep)] [&>svg]:text-[var(--color-green)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

const Alert = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>
>(({ className, variant, ...props }, ref) => (
  <div
    ref={ref}
    role="alert"
    className={cn(alertVariants({ variant }), className)}
    {...props}
  />
));
Alert.displayName = "Alert";

const AlertTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h5
    ref={ref}
    className={cn("mb-1 text-sm font-semibold leading-none tracking-tight", className)}
    {...props}
  />
));
AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("text-sm [&_p]:leading-relaxed", className)} {...props} />
));
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };
