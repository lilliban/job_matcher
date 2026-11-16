import { cn } from "@/lib/utils";

import { BELOW_LABEL, LOW_DATA_SKILLS, STATUS_LABEL, coveragePct, isLowData, skillsBasis, type MatchView } from "./matchModel";

/** Gli elementi minimi che servono a disegnare la copertura. */
type CoverageSource = Pick<
  MatchView,
  "coverage" | "skillsMeasured" | "have" | "belowThreshold"
>;

export function LowDataTag() {
  return (
    <span
      className="rounded-full border border-dashed border-line-hard px-2 py-0.5 text-xs font-medium text-ink-soft"
      title={`La percentuale è calcolata su meno di ${LOW_DATA_SKILLS} skill dell'annuncio`}
    >
      Pochi dati
    </span>
  );
}

export function BelowTag() {
  return (
    <span className="rounded-full bg-surface px-2 py-0.5 text-xs font-medium text-ink-soft">{BELOW_LABEL}</span>
  );
}

/** Etichetta dello stato di una candidatura. */
export function StatusTag({ status, className }: { status: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full bg-good-wash px-2.5 py-0.5 text-xs font-medium text-good",
        className,
      )}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

/** Barra di copertura con la percentuale; sotto la soglia la barra è teal chiaro, non ambra. */
export function CoverageBar({ m, size = "sm" }: { m: CoverageSource; size?: "sm" | "lg" }) {
  const pct = coveragePct(m);
  if (pct == null) {
    return <p className="text-sm text-ink-soft">Skill non trovate nell'annuncio: la copertura non si può misurare.</p>;
  }
  return (
    <div className="flex items-center gap-3">
      <div
        role="progressbar"
        aria-label="Copertura delle skill richieste"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={`${pct}%, ${skillsBasis(m)}`}
        className={cn("flex-1 overflow-hidden rounded-full bg-accent-wash", size === "lg" ? "h-2.5" : "h-1.5")}
      >
        {pct > 0 && (
          <div
            className={cn("jm-bar-fill h-full rounded-full", m.belowThreshold ? "bg-teal-soft" : "bg-accent")}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      <span
        className={cn(
          "shrink-0 font-mono leading-none tracking-[-0.02em] tabular-nums",
          size === "lg" ? "text-3xl" : "text-lg",
        )}
      >
        {pct}%
      </span>
    </div>
  );
}

/** Colonna in alto a destra della card: percentuale, barra corta, etichette. */
export function CardScore({ m }: { m: CoverageSource }) {
  const pct = coveragePct(m);
  if (pct == null) {
    return (
      <div className="w-24 shrink-0 text-right">
        <span className="font-mono text-lg leading-none text-ink-faint">—</span>
        <p className="mt-1 text-xs leading-snug text-ink-soft">Skill non trovate nell'annuncio</p>
      </div>
    );
  }
  const low = isLowData(m);
  return (
    <div className="flex w-24 shrink-0 flex-col items-end gap-1.5">
      <span className="font-mono text-xl leading-none tracking-[-0.02em] tabular-nums">{pct}%</span>
      <div
        role="progressbar"
        aria-label="Copertura delle skill richieste"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={low ? `${pct}%, calcolata su ${skillsBasis(m)}` : `${pct}%`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-accent-wash"
      >
        {pct > 0 && (
          <div
            className={cn("jm-bar-fill h-full rounded-full", m.belowThreshold ? "bg-teal-soft" : "bg-accent")}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      {low && <span className="font-mono text-xs text-ink-soft">{skillsBasis(m)}</span>}
      {low && <LowDataTag />}
      {m.belowThreshold && <BelowTag />}
    </div>
  );
}

const SKILL_TONE = {
  have: "border-transparent bg-good-wash text-good",
  missing: "border-line-hard text-ink",
  nice: "border-dashed border-line-hard text-ink-soft",
} as const;

export function SkillRow({
  label,
  skills,
  tone,
}: {
  label: string;
  skills: string[];
  tone: keyof typeof SKILL_TONE;
}) {
  if (skills.length === 0) return null;
  return (
    <div>
      <dt className="mb-1.5 text-xs font-medium text-ink-soft">
        {label} <span className="font-mono">({skills.length})</span>
      </dt>
      <dd className="flex flex-wrap gap-1.5">
        {skills.map((s) => (
          <span key={s} className={cn("rounded-full border px-2.5 py-1 font-mono text-xs", SKILL_TONE[tone])}>
            {s}
          </span>
        ))}
      </dd>
    </div>
  );
}
