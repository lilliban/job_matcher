import { useId } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

import { REMOVE_VALUE, STATUS_LABEL, TRACKED_STATUSES, isTracked } from "./matchModel";

/**
 * Menu dello stato di una candidatura. È un <select> nativo: su telefono apre il
 * selettore di sistema e da tastiera funziona come ci si aspetta.
 *
 * `value` è lo stato attuale; se non è uno stato da candidatura (annuncio non
 * ancora salvato, risultato di ricerca "nuovo") il menu mostra «Scegli» e
 * scegliere uno stato lo trasforma in candidatura. «Togli dalle candidature»
 * compare solo quando c'è qualcosa da togliere.
 */
export function StatusMenu({
  value,
  onChange,
  disabled,
  caption = "Stato",
  label = "Stato della candidatura",
  className,
}: {
  value: string | null | undefined;
  onChange: (next: string) => void;
  disabled?: boolean;
  /** Etichetta visibile a sinistra; null per toglierla (righe strette) */
  caption?: string | null;
  /** Nome per gli screen reader; nelle liste includi il titolo dell'annuncio */
  label?: string;
  className?: string;
}) {
  const id = useId();
  const tracked = isTracked(value);
  return (
    <div className={cn("relative", className)}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      {caption && (
        <span aria-hidden className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-xs text-ink-soft">
          {caption}
        </span>
      )}
      <select
        id={id}
        value={tracked ? value : ""}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "jm-press h-11 w-full min-w-0 appearance-none rounded-full border border-field bg-paper-2 pr-9 text-sm font-medium text-ink hover:border-accent disabled:opacity-70 sm:h-10",
          caption ? "pl-[4.25rem]" : "pl-4",
        )}
      >
        {!tracked && (
          <option value="" disabled>
            Scegli
          </option>
        )}
        {TRACKED_STATUSES.map((s) => (
          <option key={s} value={s}>
            {STATUS_LABEL[s]}
          </option>
        ))}
        {tracked && <option value={REMOVE_VALUE}>Togli dalle candidature</option>}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft"
      />
    </div>
  );
}
