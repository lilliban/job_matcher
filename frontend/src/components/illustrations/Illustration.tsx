import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Colori delle illustrazioni: solo token di tokens.css. Tre teal, carta,
 * bianco e il prugna come unico accento caldo.
 */
export const C = {
  deep: "var(--color-teal-deep)",
  mid: "var(--color-teal-mid)",
  soft: "var(--color-teal-soft)",
  paper: "var(--color-paper)",
  white: "var(--color-paper-2)",
  plum: "var(--color-plum)",
} as const;

export interface IllustrationProps {
  className?: string;
}

/**
 * Cornice comune: SVG decorativo, nascosto agli screen reader, senza testo.
 * Forme piatte con angoli arrotondati: niente ombre, gradienti o contorni scuri.
 * La larghezza la decide chi lo usa (className); l'altezza segue il viewBox.
 */
export function Illustration({
  className,
  children,
}: IllustrationProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 160 120"
      aria-hidden="true"
      focusable="false"
      className={cn("block h-auto shrink-0 select-none", className)}
    >
      {children}
    </svg>
  );
}

/** Macchia di fondo: dà alle forme bianche un piano su cui stare, anche sulla carta. */
export function Backdrop() {
  return <rect x="6" y="14" width="148" height="100" rx="50" fill={C.soft} fillOpacity={0.4} />;
}
