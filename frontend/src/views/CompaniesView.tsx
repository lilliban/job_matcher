import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Building2, Check, Loader2, Plus, Search, Sparkles, Trash2 } from "lucide-react";

import { Hint, PageHeader } from "@/components/Page";
import { Buildings } from "@/components/illustrations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/api/client";
import {
  useAddPreferredCompany,
  useBrowseCompanies,
  useCompanyCatalog,
  useDeletePreferredCompany,
  usePreferredCompanies,
  useSearchCompaniesByName,
} from "@/api/queries";
import type { CompanySuggestion } from "@/api/schemas";
import { useCurrentUser } from "@/hooks/useCurrentUser";

const SIZE_LABEL: Record<string, string> = { small: "Piccola", medium: "Media", large: "Grande" };

export function CompaniesView() {
  const { userId, isBooting } = useCurrentUser();

  if (isBooting) return <div className="text-ink-faint">Caricamento…</div>;
  if (!userId) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <Hint>Prima crea il tuo profilo, poi scegli le aziende che ti interessano.</Hint>
      </div>
    );
  }
  return <CompaniesWorkspace userId={userId} />;
}

function CompaniesWorkspace({ userId }: { userId: string }) {
  const catalog = useCompanyCatalog();
  const list = usePreferredCompanies(userId);
  const addCompany = useAddPreferredCompany(userId);
  const removeCompany = useDeletePreferredCompany(userId);
  const browse = useBrowseCompanies(userId);
  const byName = useSearchCompaniesByName(userId);

  const [scope, setScope] = useState<string | null>(null);
  const [sector, setSector] = useState<string | null>(null);
  const [country, setCountry] = useState("IT");
  const [results, setResults] = useState<CompanySuggestion[]>([]);
  const [nameQuery, setNameQuery] = useState("");
  const resultsRef = useRef<HTMLDivElement>(null);

  const scopeInfo = catalog.data?.scopes.find((s) => s.key === scope);
  const mine = list.data ?? [];
  const mineNames = useMemo(() => new Set(mine.map((c) => c.name.toLowerCase())), [mine]);
  const idByName = useMemo(() => new Map(mine.map((c) => [c.name.toLowerCase(), c.id])), [mine]);

  // Carica le aziende appena ambito e settore sono scelti.
  const fetchCompanies = async (more = false) => {
    if (!scope || !sector) return;
    try {
      const found = await browse.mutateAsync({
        scope,
        sector,
        country_code: scopeInfo?.needs_country ? country : null,
        exclude: more ? results.map((r) => r.name) : [],
        limit: 10,
      });
      setResults(more ? [...results, ...found] : found);
      if (found.length === 0) toast.message("Non ho trovato altre aziende per questa scelta");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore nella ricerca");
    }
  };

  useEffect(() => {
    if (scope && sector) {
      setResults([]);
      void fetchCompanies(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, sector, country]);

  const toggle = async (c: CompanySuggestion) => {
    const key = c.name.toLowerCase();
    try {
      if (mineNames.has(key)) {
        const id = idByName.get(key);
        if (id) await removeCompany.mutateAsync(id);
      } else {
        await addCompany.mutateAsync({
          name: c.name,
          country: c.country ?? null,
          size: c.size ?? null,
          sector: c.sector ?? null,
          website: c.website ?? null,
          source: c.source ?? "catalog",
        });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore");
    }
  };

  const addAll = async () => {
    const todo = results.filter((r) => !mineNames.has(r.name.toLowerCase()));
    for (const c of todo) await toggle(c);
    if (todo.length) toast.success(`${todo.length} aziende aggiunte`);
  };

  const searchByName = async () => {
    const q = nameQuery.trim();
    if (q.length < 2) return;
    try {
      const found = await byName.mutateAsync(q);
      setScope(null);
      setSector(null);
      setResults(found);
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
      if (found.length === 0) toast.message("Nessuna azienda trovata con questo nome");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore nella ricerca");
    }
  };

  return (
    <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-8">
        <PageHeader
          title="Aziende"
          lead="Scegli tipo di azienda e settore: ti mostro quelle giuste e costruisci la tua lista."
        />

        {/* ------- passo 1 ------- */}
        <section aria-labelledby="step-scope" className="space-y-3">
          <StepTitle n={1} id="step-scope" title="Che tipo di azienda?" />
          {catalog.isLoading ? (
            <p className="text-sm text-ink-faint">Carico…</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {(catalog.data?.scopes ?? []).map((s) => (
                <OptionCard
                  key={s.key}
                  active={scope === s.key}
                  title={s.label}
                  hint={s.hint}
                  onClick={() => setScope(s.key)}
                />
              ))}
            </div>
          )}
          {scopeInfo?.needs_country && (
            <label className="flex items-center gap-3 text-sm">
              <span className="text-ink-soft">Di quale paese?</span>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="h-11 rounded-xl border border-field bg-paper-2 px-3 text-sm sm:h-10"
              >
                {(catalog.data?.countries ?? []).map((c) => (
                  <option key={c.code} value={c.code}>{c.name}</option>
                ))}
              </select>
            </label>
          )}
        </section>

        {/* ------- passo 2 ------- */}
        <section aria-labelledby="step-sector" className="space-y-3">
          <StepTitle n={2} id="step-sector" title="In che settore?" />
          {!scope && (
            <p id="sector-hint" className="max-w-2xl rounded-xl bg-surface px-4 py-2.5 text-sm text-ink">
              Scegli prima un tipo di azienda.
            </p>
          )}
          <div className="flex flex-wrap gap-2" aria-describedby={scope ? undefined : "sector-hint"}>
            {(catalog.data?.sectors ?? []).map((s) => (
              <button
                key={s.key}
                type="button"
                disabled={!scope}
                onClick={() => setSector(s.key)}
                className={
                  "jm-press inline-flex min-h-10 items-center rounded-full border px-4 py-2 text-sm " +
                  // Disabilitati ma leggibili: testo ink-soft su superficie (contrasto > 4.5:1)
                  "disabled:cursor-not-allowed disabled:border-dashed disabled:border-line-hard disabled:bg-surface disabled:text-ink-soft " +
                  (sector === s.key
                    ? "border-accent bg-accent text-paper-2"
                    : "border-line-hard bg-paper-2 hover:border-accent hover:text-accent")
                }
              >
                {s.label}
              </button>
            ))}
          </div>
        </section>

        {/* ------- passo 3 ------- */}
        <section ref={resultsRef} aria-labelledby="step-results" className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <StepTitle n={3} id="step-results" title="Scegli le aziende" />
            {results.length > 0 && (
              <Button size="sm" variant="outline" onClick={addAll}>
                <Plus className="mr-1 h-4 w-4" /> Aggiungi tutte
              </Button>
            )}
          </div>

          {browse.isPending && results.length === 0 ? (
            <SkeletonGrid />
          ) : results.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-line-hard bg-paper-2 px-6 py-6 text-center text-sm text-ink-soft">
              <Buildings className="w-24 sm:w-28" />
              {scope && sector
                ? "Nessun risultato."
                : "Scegli un tipo e un settore e qui compariranno le aziende."}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {results.map((c) => (
                  <CompanyCard
                    key={c.name}
                    company={c}
                    selected={mineNames.has(c.name.toLowerCase())}
                    onToggle={() => toggle(c)}
                  />
                ))}
              </div>
              {scope && sector && (
                <div className="flex justify-center pt-2">
                  <Button variant="outline" onClick={() => fetchCompanies(true)} disabled={browse.isPending}>
                    {browse.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Mostrane altre
                  </Button>
                </div>
              )}
            </>
          )}
        </section>

        {/* ------- ricerca per nome ------- */}
        <section className="rounded-2xl border border-line bg-paper-2 p-5">
          <p className="mb-2 text-sm font-medium">Sai già quale azienda cerchi?</p>
          <div className="flex gap-2">
            <Input
              value={nameQuery}
              onChange={(e) => setNameQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && searchByName()}
              placeholder="Es. Ferrari, Bosch, Datadog…"
              aria-label="Cerca un'azienda per nome"
            />
            <Button variant="outline" onClick={searchByName} disabled={byName.isPending}>
              {byName.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              <span className="ml-1">Cerca</span>
            </Button>
          </div>
        </section>
      </div>

      {/* ------- la mia lista ------- */}
      <aside className="space-y-4 lg:sticky lg:top-8 lg:self-start">
        <MyList
          companies={mine}
          onRemove={(id) => removeCompany.mutate(id)}
          loading={list.isLoading}
        />
        <SimilarToMine
          userId={userId}
          names={mine.map((c) => c.name)}
          mineNames={mineNames}
          onAdd={toggle}
        />
      </aside>
    </div>
  );
}

/* -------------------------------- pezzi UI -------------------------------- */

function StepTitle({ n, title, id }: { n: number; title: string; id: string }) {
  return (
    <h2 id={id} className="flex items-center gap-3 jm-h2">
      <span className="grid h-7 w-7 place-items-center rounded-full bg-surface font-mono text-xs font-medium text-ink">
        {n}
      </span>
      {title}
    </h2>
  );
}

function OptionCard({
  active, title, hint, onClick,
}: { active: boolean; title: string; hint: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={
        "jm-press rounded-2xl border p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 " +
        (active
          ? "border-accent bg-accent-wash"
          : "border-line-hard bg-paper-2 hover:border-accent")
      }
    >
      <span className="flex items-center justify-between">
        <span className="font-medium">{title}</span>
        {active && <Check className="h-4 w-4 text-accent" />}
      </span>
      <span className="mt-1 block text-xs text-ink-soft">{hint}</span>
    </button>
  );
}

function CompanyCard({
  company, selected, onToggle,
}: { company: CompanySuggestion; selected: boolean; onToggle: () => void }) {
  return (
    <div
      className={
        "flex items-start gap-3 rounded-2xl border p-4 transition-colors " +
        (selected ? "border-accent bg-accent-wash/50" : "border-line bg-paper-2")
      }
    >
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-surface text-ink-soft">
        <Building2 className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{company.name}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {company.sector && <Badge variant="outline">{company.sector}</Badge>}
          {company.size && <Badge variant="outline">{SIZE_LABEL[company.size] ?? company.size}</Badge>}
        </div>
        {company.reason && <p className="mt-2 text-xs text-ink-soft">{company.reason}</p>}
      </div>
      <Button
        size="sm"
        variant={selected ? "default" : "outline"}
        onClick={onToggle}
        aria-pressed={selected}
        aria-label={selected ? `Togli ${company.name} dalla lista` : `Aggiungi ${company.name} alla lista`}
      >
        {selected ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
      </Button>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2" aria-busy="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-[88px] animate-pulse rounded-2xl border border-line bg-paper-2" />
      ))}
    </div>
  );
}

function MyList({
  companies, onRemove, loading,
}: {
  companies: Array<{ id: string; name: string; sector?: string | null }>;
  onRemove: (id: string) => void;
  loading: boolean;
}) {
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="jm-h2">La mia lista</h2>
        <span className="font-mono text-xs text-ink-faint">{companies.length}</span>
      </div>
      {loading ? (
        <p className="text-sm text-ink-faint">Carico…</p>
      ) : companies.length === 0 ? (
        <div className="flex flex-col items-start gap-3">
          <Buildings className="w-24" />
          <p className="text-sm text-ink-soft">
            Ancora vuota. Aggiungi le aziende che ti interessano: le userai nelle ricerche.
          </p>
        </div>
      ) : (
        <ul className="max-h-[320px] space-y-1 overflow-y-auto pr-1">
          {companies.map((c) => (
            <li key={c.id} className="flex items-center justify-between rounded-xl py-1 pl-3 pr-1 text-sm hover:bg-paper">
              <span className="min-w-0">
                <span className="block truncate">{c.name}</span>
                {c.sector && <span className="block truncate text-xs text-ink-faint">{c.sector}</span>}
              </span>
              <button
                type="button"
                onClick={() => onRemove(c.id)}
                aria-label={`Rimuovi ${c.name}`}
                className="jm-press grid h-10 w-10 shrink-0 place-items-center rounded-full text-ink-faint hover:bg-bad-wash hover:text-bad"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Suggerimenti "simili a quelle che hai scelto": si aggiornano da soli
 *  quando la lista cambia, e restano in cache per la stessa lista. */
function SimilarToMine({
  userId, names, mineNames, onAdd,
}: {
  userId: string;
  names: string[];
  mineNames: Set<string>;
  onAdd: (c: CompanySuggestion) => void;
}) {
  // si aspetta che l'utente finisca di cliccare prima di chiedere all'AI
  const [debounced, setDebounced] = useState<string[]>(names);
  const sig = [...names].sort().join("|");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(names), 900);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  const key = [...debounced].sort().join("|");
  const similar = useQuery({
    queryKey: ["similar-companies", userId, key],
    queryFn: () =>
      api<CompanySuggestion[]>(`/api/users/${userId}/companies/similar`, {
        method: "POST",
        json: { selected_companies: debounced, limit: 6 },
      }),
    enabled: debounced.length > 0,
    staleTime: Infinity,
  });

  if (names.length === 0) return null;
  const items = (similar.data ?? []).filter(
    (c) => !mineNames.has(c.name.toLowerCase()) && c.exists_online !== false,
  );

  return (
    <Card className="p-5">
      <h2 className="mb-1 flex items-center gap-2 jm-h2">
        <Sparkles className="h-4 w-4 text-accent" /> Simili alle tue
      </h2>
      <p className="mb-3 text-xs text-ink-soft">In base alle aziende che hai scelto.</p>
      {similar.isFetching ? (
        <p className="flex items-center gap-2 text-sm text-ink-soft">
          <Loader2 className="h-4 w-4 animate-spin" /> Cerco aziende simili…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-ink-faint">Nessun suggerimento per ora.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((c) => (
            <li key={c.name} className="flex items-center justify-between gap-2 text-sm">
              <span className="min-w-0">
                <span className="block truncate">{c.name}</span>
                {c.reason && <span className="block truncate text-xs text-ink-faint" title={c.reason}>{c.reason}</span>}
              </span>
              <Button size="sm" variant="outline" onClick={() => onAdd(c)} aria-label={`Aggiungi ${c.name}`}>
                <Plus className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
