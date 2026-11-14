import type { ReactNode } from "react";

/**
 * Avatar 2D dell'assistente: un omino stilizzato che accompagna l'utente.
 * SVG inline (nessun asset da caricare), colori dai token del tema.
 */
export function Avatar({ size = 72, waving = false }: { size?: number; waving?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      role="img"
      aria-label="Il tuo assistente"
      className="shrink-0"
    >
      <circle cx="60" cy="60" r="58" fill="var(--color-accent-wash)" />
      {/* busto */}
      <path
        d="M16 112c2-24 20-36 44-36s42 12 44 36a58 58 0 0 1-88 0z"
        fill="var(--color-accent)"
      />
      <path d="M48 78l12 14 12-14" fill="none" stroke="#fff" strokeWidth="3" strokeLinejoin="round" />
      {/* collo */}
      <rect x="53" y="66" width="14" height="14" rx="6" fill="#f0c4a0" />
      {/* testa */}
      <ellipse cx="60" cy="48" rx="22" ry="24" fill="#f6d2b3" />
      {/* capelli */}
      <path
        d="M37 46c-2-18 10-28 24-28s26 9 22 28c-4-8-9-12-16-13-9 5-20 6-30 13z"
        fill="var(--color-ink)"
      />
      {/* occhi con battito */}
      <g fill="var(--color-ink)" className="jm-blink">
        <ellipse cx="51" cy="50" rx="2.6" ry="3.2" />
        <ellipse cx="69" cy="50" rx="2.6" ry="3.2" />
      </g>
      {/* sorriso e guance */}
      <path
        d="M52 60c4 5 12 5 16 0"
        fill="none"
        stroke="var(--color-ink)"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <circle cx="45" cy="58" r="3.4" fill="#f2a58e" opacity=".55" />
      <circle cx="75" cy="58" r="3.4" fill="#f2a58e" opacity=".55" />
      {waving && (
        <g className="jm-wave" style={{ transformOrigin: "98px 92px" }}>
          <rect x="92" y="66" width="9" height="28" rx="4.5" fill="var(--color-accent)" />
          <circle cx="96.5" cy="63" r="6.5" fill="#f6d2b3" />
        </g>
      )}
    </svg>
  );
}

/** Avatar con fumetto: il modo in cui l'app "parla" all'utente. */
export function Guide({
  children,
  waving = false,
  size = 72,
}: {
  children: ReactNode;
  waving?: boolean;
  size?: number;
}) {
  return (
    <div className="flex items-center gap-4">
      <Avatar size={size} waving={waving} />
      <div className="relative max-w-xl rounded border border-line bg-paper-2 px-5 py-4 shadow-sm">
        <span
          aria-hidden
          className="absolute -left-2 top-1/2 h-4 w-4 -translate-y-1/2 rotate-45 border-b border-l border-line bg-paper-2"
        />
        <div className="relative text-[15px] leading-snug text-ink">{children}</div>
      </div>
    </div>
  );
}
