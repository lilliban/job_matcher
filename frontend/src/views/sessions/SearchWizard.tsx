import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Building2, Check, Globe2, Loader2, Newspaper, Plus, Rocket, Sparkles, X } from "lucide-react";

import { Hint } from "@/components/Page";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useAddHardSkill,
  useCreateSession,
  useGeoTree,
  useHardSkills,
  usePreferredCompanies,
  useRoleAdvice,
  useRoleGap,
  useStartSession,
} from "@/api/queries";
import type { SearchMode } from "@/api/schemas";
import { useAppState } from "@/stores/useAppState";

const CONTRACTS = [
  ["", "Indifferente"],
  ["full-time", "Full time"],
  ["part-time", "Part time"],
  ["internship", "Stage"],
  ["freelance", "Freelance"],
] as const;

const selectClass =
  "h-11 w-full rounded-xl border border-field bg-paper-2 px-3 text-sm sm:h-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40";

interface Country {
  code: string;
  name: string;
}

function extractCountries(tree: unknown): Country[] {
  const t = (tree ?? {}) as { countries?: Country[] };
  return (Array.isArray(t.countries) ? t.countries : [])
    .filter((c) => c && typeof c.code === "string" && typeof c.name === "string")
    .sort((a, b) => countryRank(a.code) - countryRank(b.code) || a.name.localeCompare(b.name, "it"));
}

// Paesi in cima al menu, in quest'ordine; gli altri seguono in ordine alfabetico.
const TOP_COUNTRIES = ["CH", "DE", "NL"];
function countryRank(code: string): number {
  const i = TOP_COUNTRIES.indexOf(code);
  return i === -1 ? TOP_COUNTRIES.length : i;
}

export function SearchWizard({ userId }: { userId: string }) {
  const navigate = useNavigate();
  const setSessionId = useAppState((s) => s.setSessionId);
  const newsSeenAt = useAppState((s) => s.newsSeenAt);
  const markNewsSeen = useAppState((s) => s.markNewsSeen);

  const advice = useRoleAdvice(userId, newsSeenAt);
  const geo = useGeoTree();
  const mine = usePreferredCompanies(userId);
  const hardSkills = useHardSkills(userId);
  const addSkill = useAddHardSkill(userId);
  const createSession = useCreateSession(userId);
  const startSession = useStartSession(userId);

  const [mode, setMode] = useState<"companies" | "market">("market");
  const [role, setRole] = useState("");          // testo libero o ruolo scelto
  const [anyRole, setAnyRole] = useState(false); // "qualsiasi ruolo adatto a me"
  const [country, setCountry] = useState("CH");
  const [zone, setZone] = useState("");
  const [contract, setContract] = useState("");
  const [threshold, setThreshold] = useState(50);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [gapDismissed, setGapDismissed] = useState<string | null>(null);

  const countries = extractCountries(geo.data);
  const myCompanies = mine.data ?? [];
  const roleChosen = anyRole ? "" : role.trim();
  const gap = useRoleGap(userId, roleChosen);

  const ownedSkills = new Set((hardSkills.data ?? []).map((s) => s.name.toLowerCase()));
  const news = advice.data?.news;
  const hasNews = !!news && news.matching_roles > 0;

  const needsCompanies = mode === "companies" && myCompanies.length === 0;
  const needsRole = !anyRole && roleChosen === "" && mode === "market";
  const canLaunch =
    !needsCompanies && !needsRole && !createSession.isPending && !startSession.isPending;

  function pickRole(r: string) {
    setAnyRole(false);
    setRole(r);
    setGapDismissed(null);
  }

  async function launch() {
    const searchMode: SearchMode = mode;
    try {
      const created = await createSession.mutateAsync({
        role_title: roleChosen,
        search_mode: searchMode,
        preferred_country: mode === "market" ? country || null : null,
        location_pref: mode === "market" ? zone.trim() || null : null,
        contract_type: contract || null,
        match_threshold: threshold / 100,
        hard_skills: [],
        companies:
          mode === "companies"
            ? myCompanies.map((c) => ({
                name: c.name,
                country: c.country ?? null,
                size: c.size ?? null,
                sector: c.sector ?? null,
                website: c.website ?? null,
                source: "list",
              }))
            : [],
      });
      await startSession.mutateAsync(created.id);
      setSessionId(created.id);
      markNewsSeen();
      toast.success("Ricerca avviata: ti porto allo storico");
      navigate("/storico");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Non sono riuscito ad avviare la ricerca");
    }
  }

  const summary = (() => {
    const what = anyRole || !roleChosen ? "qualsiasi ruolo adatto al tuo profilo" : `«${roleChosen}»`;
    if (mode === "companies") return `Cercherò ${what} nelle ${myCompanies.length} aziende della tua lista.`;
    const where = countries.find((c) => c.code === country)?.name ?? "tutti i paesi";
    return `Cercherò ${what} su tutte le aziende, in ${zone.trim() ? `${zone.trim()} (${where})` : where}.`;
  })();

  return (
    <div className="space-y-6">
      <Hint>
        Scegli <strong>dove</strong> e <strong>cosa</strong> cercare. Appena parte la ricerca ti porto
        allo Storico.
      </Hint>

      {hasNews && (
        <NewsBanner
          total={news!.matching_roles}
          sample={news!.sample}
          since={newsSeenAt}
          onDismiss={markNewsSeen}
        />
      )}

      <Card className="space-y-8 p-5 md:p-8">
        {/* 1 — dove */}
        <Step n={1} title="Dove cerchiamo?">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <ModeCard
              active={mode === "market"}
              icon={<Globe2 className="h-5 w-5" />}
              title="Su tutte le aziende"
              text="Portali di lavoro e archivio annunci: qualunque azienda."
              onClick={() => setMode("market")}
            />
            <ModeCard
              active={mode === "companies"}
              icon={<Building2 className="h-5 w-5" />}
              title="Nelle mie aziende"
              text={
                myCompanies.length
                  ? `Solo le ${myCompanies.length} aziende della tua lista.`
                  : "Non hai ancora una lista: creala nella sezione Aziende."
              }
              onClick={() => setMode("companies")}
            />
          </div>
          {needsCompanies && (
            <p className="text-sm text-warn">
              La tua lista è vuota.{" "}
              <button type="button" className="font-medium underline underline-offset-4" onClick={() => navigate("/aziende")}>
                Vai ad Aziende
              </button>{" "}
              per sceglierne qualcuna, oppure cerca su tutto il mercato.
            </p>
          )}
        </Step>

        {/* 2 — cosa */}
        <Step n={2} title="Che lavoro?">
          <div className="space-y-3">
            {advice.isLoading ? (
              <p className="flex items-center gap-2 text-sm text-ink-soft">
                <Loader2 className="h-4 w-4 animate-spin" /> Guardo che ruoli ti stanno bene…
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {(advice.data?.roles ?? []).map((r) => (
                  <RoleChip
                    key={r.role}
                    active={!anyRole && role === r.role}
                    label={r.role}
                    news={r.new_postings}
                    title={r.reason}
                    onClick={() => pickRole(r.role)}
                  />
                ))}
                <RoleChip
                  active={anyRole}
                  label="Qualsiasi ruolo adatto a me"
                  icon={<Sparkles className="h-3.5 w-3.5" />}
                  title="Cerco quello che il tuo profilo sa fare, senza fissare un titolo"
                  onClick={() => {
                    setAnyRole(true);
                    setRole("");
                  }}
                />
              </div>
            )}
            <Input
              value={anyRole ? "" : role}
              disabled={anyRole}
              onChange={(e) => {
                setRole(e.target.value);
                setGapDismissed(null);
              }}
              placeholder="…oppure scrivi un ruolo (es. Data Analyst)"
              aria-label="Ruolo da cercare"
            />
            {!anyRole && role && advice.data?.roles.find((r) => r.role === role)?.reason && (
              <p className="text-xs text-ink-soft">
                {advice.data.roles.find((r) => r.role === role)!.reason}
              </p>
            )}
          </div>

          {gap.data?.show && gapDismissed !== roleChosen && (
            <GapNotice
              role={roleChosen}
              missing={gap.data.missing.filter((m) => !ownedSkills.has(m.toLowerCase()))}
              onAdd={(name) =>
                addSkill.mutate(
                  { name, level: "intermediate", years_exp: 1, acquired_via: "work" },
                  { onSuccess: () => toast.success(`${name} aggiunta al profilo`) },
                )
              }
              onDismiss={() => setGapDismissed(roleChosen)}
            />
          )}
        </Step>

        {/* 3 — dove (geografia), solo mercato */}
        {mode === "market" && (
          <Step n={3} title="In che zona?">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="space-y-1.5 text-sm">
                <span className="text-ink-soft">Paese</span>
                <select className={selectClass} value={country} onChange={(e) => setCountry(e.target.value)}>
                  <option value="">Ovunque</option>
                  {countries.map((c) => (
                    <option key={c.code} value={c.code}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="text-ink-soft">Città o zona (facoltativa)</span>
                <Input value={zone} onChange={(e) => setZone(e.target.value)} placeholder="Milano, Berlin…" />
              </label>
            </div>
          </Step>
        )}

        {/* avanzate */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="inline-flex h-10 items-center text-sm text-ink-soft underline underline-offset-4 hover:text-ink"
            aria-expanded={showAdvanced}
          >
            {showAdvanced ? "Nascondi opzioni" : "Altre opzioni (contratto, precisione)"}
          </button>
          {showAdvanced && (
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="space-y-1.5 text-sm">
                <span className="text-ink-soft">Contratto</span>
                <select className={selectClass} value={contract} onChange={(e) => setContract(e.target.value)}>
                  {CONTRACTS.map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="text-ink-soft">Mostrami solo annunci compatibili almeno al {threshold}%</span>
                <input
                  type="range" min={0} max={100} step={5} value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="w-full accent-accent"
                />
              </label>
            </div>
          )}
        </div>

        {/* lancio */}
        <div className="flex flex-col gap-3 border-t border-line pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink-soft" aria-live="polite">
            {needsRole
              ? "Scegli un ruolo o «Qualsiasi ruolo adatto a me» per avviare la ricerca."
              : needsCompanies
                ? "La tua lista aziende è vuota: aggiungine qualcuna o cerca su tutte le aziende."
                : summary}
          </p>
          <Button size="lg" onClick={launch} disabled={!canLaunch} className="w-full sm:w-auto">
            {createSession.isPending || startSession.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Rocket className="mr-2 h-4 w-4" />
            )}
            Avvia la ricerca
          </Button>
        </div>
      </Card>
    </div>
  );
}

/* -------------------------------- pezzi UI -------------------------------- */

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="jm-h2 flex items-center gap-3">
        <span className="grid h-7 w-7 place-items-center rounded-full bg-surface font-mono text-xs font-medium text-ink">
          {n}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function ModeCard({
  active, icon, title, text, onClick,
}: { active: boolean; icon: React.ReactNode; title: string; text: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={
        "jm-press flex items-start gap-3 rounded-2xl border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 " +
        (active ? "border-accent bg-accent-wash" : "border-line bg-paper-2 hover:border-line-hard")
      }
    >
      <span className={"mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full " + (active ? "bg-accent text-paper" : "bg-paper text-ink-soft")}>
        {icon}
      </span>
      <span>
        <span className="flex items-center gap-2 font-medium">
          {title}
          {active && <Check className="h-4 w-4 text-accent" />}
        </span>
        <span className="mt-0.5 block text-xs text-ink-soft">{text}</span>
      </span>
    </button>
  );
}

function RoleChip({
  active, label, news, icon, title, onClick,
}: {
  active: boolean; label: string; news?: number; icon?: React.ReactNode;
  title?: string; onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={
        "jm-press flex min-h-10 items-center gap-2 rounded-full border px-4 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 " +
        (active
          ? "border-accent bg-accent text-paper"
          : "border-line bg-paper-2 hover:border-accent hover:text-accent")
      }
    >
      {icon}
      {label}
      {!!news && news > 0 && (
        <span className={"rounded-full px-2 py-0.5 text-xs font-medium " + (active ? "bg-paper-2/20" : "bg-good-wash text-good")}>
          {news > 99 ? "99+" : news} nuovi
        </span>
      )}
    </button>
  );
}

function NewsBanner({
  total, sample, since, onDismiss,
}: {
  total: number;
  sample: Array<{ title: string; company_name: string; location: string | null }>;
  since: string | null;
  onDismiss: () => void;
}) {
  return (
    <div className="flex items-start gap-4 rounded-2xl bg-surface p-5">
      <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent text-paper-2">
        <Newspaper className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-ink">
          {total} {total === 1 ? "nuovo annuncio" : "nuovi annunci"} per i tuoi ruoli
          {since ? " dall'ultima volta" : ""}
        </p>
        {sample.length > 0 && (
          <ul className="mt-1.5 space-y-0.5 text-sm text-ink-soft">
            {sample.slice(0, 3).map((s, i) => (
              <li key={i} className="truncate">
                {s.title} · {s.company_name}
                {s.location ? ` · ${s.location}` : ""}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-ink-soft">Lancia una ricerca qui sotto per vedere come ti stanno.</p>
      </div>
      <button type="button" onClick={onDismiss} aria-label="Nascondi novità" className="jm-press -m-2 grid h-10 w-10 shrink-0 place-items-center rounded-full text-ink-faint hover:bg-paper-2 hover:text-ink">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

/** Compare solo con una carenza seria (decide il backend): negli altri casi
 *  le competenze mancanti si vedono comunque nel dettaglio dei match. */
function GapNotice({
  role, missing, onAdd, onDismiss,
}: { role: string; missing: string[]; onAdd: (name: string) => void; onDismiss: () => void }) {
  if (missing.length === 0) return null;
  return (
    <div className="rounded-2xl border border-warn/30 bg-warn-wash p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm">
          Per <strong>{role}</strong> di solito servono parecchie competenze che non ho nel tuo profilo.
          Se ne conosci qualcuna, aggiungila: troverò annunci più adatti. Altrimenti cerca pure, ti dirò
          cosa ti manca per ogni annuncio.
        </p>
        <button type="button" onClick={onDismiss} aria-label="Chiudi avviso" className="jm-press -m-2 grid h-10 w-10 shrink-0 place-items-center rounded-full text-ink-faint hover:bg-paper-2 hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {missing.slice(0, 8).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => onAdd(m)}
            className="jm-press inline-flex h-10 items-center gap-1 rounded-full border border-warn/40 bg-paper-2 px-4 text-sm hover:bg-warn hover:text-paper-2"
          >
            <Plus className="h-3 w-3" /> Ho {m}
          </button>
        ))}
      </div>
    </div>
  );
}

