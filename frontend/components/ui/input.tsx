import { type InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
