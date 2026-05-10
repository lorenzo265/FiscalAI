import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-md border p-4 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:size-4 [&>svg~*]:pl-7",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-card)] border-[var(--color-line-2)] text-[var(--color-txt)] [&>svg]:text-[var(--color-txt-2)]",
        info: "bg-[var(--color-blue-d)] border-[rgba(77,142,255,0.22)] text-[var(--color-blue)] [&>svg]:text-[var(--color-blue)]",
        warn: "bg-[var(--color-amber-d)] border-[rgba(255,184,77,0.22)] text-[var(--color-amber)] [&>svg]:text-[var(--color-amber)]",
        destructive:
          "bg-[var(--color-red-d)] border-[rgba(255,85,102,0.22)] text-[var(--color-red)] [&>svg]:text-[var(--color-red)]",
        ok: "bg-[var(--color-lime-d)] border-[rgba(163,255,107,0.22)] text-[var(--color-lime)] [&>svg]:text-[var(--color-lime)]",
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
