import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "secondary" | "outline" | "ghost" | "destructive";

const variantClasses: Record<Variant, string> = {
  default: "bg-accent text-accent-foreground hover:brightness-110",
  secondary: "bg-[var(--border)] text-foreground hover:opacity-80",
  outline: "border border-[var(--border)] bg-surface text-foreground hover:border-accent hover:text-accent",
  ghost: "text-foreground hover:bg-[var(--surface-hover)]",
  destructive: "bg-red-600 text-white hover:bg-red-700",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[9px] px-4 py-2.5 text-[13px] font-semibold transition-colors disabled:opacity-50 disabled:pointer-events-none",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
