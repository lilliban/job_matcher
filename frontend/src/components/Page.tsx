import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Intestazione di pagina condivisa: titolo + una riga di contesto.
 * `art` è un'illustrazione piccola: accanto al titolo da 640px in su, sopra
 * il titolo e più piccola su telefono, così non schiaccia il testo.
 */
export function PageHeader({
  title,
  lead,
  actions,
  art,
}: {
  title: string;
  lead?: ReactNode;
  actions?: ReactNode;
  art?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      {art && <div className="w-20 shrink-0 sm:order-last sm:w-32">{art}</div>}
      <div className="min-w-0 flex-1">
        <h1 className="jm-title">{title}</h1>
        {lead && <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">{lead}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

/**
 * Messaggio guida: una frase corta in un riquadro semplice.
 * Prende il posto della vecchia mascotte con il fumetto.
 */
export function Hint({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      role="note"
      className={cn(
        "max-w-2xl rounded-xl border border-line bg-surface px-4 py-3 text-[15px] leading-snug text-ink",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * Stato vuoto o di attesa con illustrazione: l'immagine sopra su telefono,
 * a sinistra del testo da 640px in su. Dimensione contenuta di proposito.
 */
export function EmptyState({
  art,
  children,
  className,
  status = false,
}: {
  art: ReactNode;
  children: ReactNode;
  className?: string;
  /** true per uno stato di caricamento: viene annunciato agli screen reader */
  status?: boolean;
}) {
  return (
    <div
      role={status ? "status" : undefined}
      className={cn("flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:gap-5", className)}
    >
      <div className="w-24 shrink-0 sm:w-28">{art}</div>
      <div className="min-w-0 max-w-xl text-[15px] leading-snug text-ink-soft">{children}</div>
    </div>
  );
}

/** Stato di caricamento testuale, annunciato agli screen reader. */
export function Loading({ children = "Caricamento…" }: { children?: ReactNode }) {
  return (
    <p role="status" className="text-ink-soft">
      {children}
    </p>
  );
}
