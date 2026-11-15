import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Intestazione di pagina condivisa: titolo + una riga di contesto. */
export function PageHeader({
  title,
  lead,
  actions,
}: {
  title: string;
  lead?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
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

/** Stato di caricamento testuale, annunciato agli screen reader. */
export function Loading({ children = "Caricamento…" }: { children?: ReactNode }) {
  return (
    <p role="status" className="text-ink-soft">
      {children}
    </p>
  );
}
