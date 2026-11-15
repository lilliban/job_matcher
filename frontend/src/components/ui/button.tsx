import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Tutti i pulsanti sono alti almeno 40px (44px su telefono) e hanno forma a
// pillola come in "I tuoi match". Lo stato disabilitato resta leggibile
// (bordo tratteggiato, testo pieno) invece di sbiadire tutto.
const buttonVariants = cva(
  "jm-press inline-flex shrink-0 items-center justify-center gap-2 rounded-full text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2 focus-visible:ring-offset-paper disabled:pointer-events-none",
  {
    variants: {
      variant: {
        default:
          "bg-accent text-paper-2 hover:bg-accent-ink disabled:border disabled:border-dashed disabled:border-line-hard disabled:bg-surface disabled:text-ink-soft",
        outline:
          "border border-line-hard bg-paper-2 text-ink hover:border-accent disabled:border-dashed disabled:text-ink-soft",
        ghost: "text-ink-soft hover:bg-surface hover:text-ink disabled:text-ink-faint",
        destructive: "bg-bad text-paper-2 hover:bg-bad/90",
        link: "rounded-sm text-accent underline underline-offset-4 hover:text-accent-ink",
        secondary: "bg-surface text-ink hover:bg-line",
      },
      size: {
        default: "h-11 px-5 sm:h-10",
        sm: "h-11 px-4 sm:h-10",
        lg: "h-12 px-6 text-[15px]",
        icon: "h-11 w-11 sm:h-10 sm:w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
