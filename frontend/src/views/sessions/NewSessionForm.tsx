import { useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  useCreateSession,
  useGeoTree,
  useSuggestSkillsForRole,
} from "@/api/queries";
import { useAppState } from "@/stores/useAppState";

const CONTRACTS = [
  ["", "Indifferente"],
  ["full-time", "Full time"],
  ["part-time", "Part time"],
  ["internship", "Stage"],
  ["freelance", "Freelance"],
] as const;

const selectClass =
  "h-9 w-full rounded-sm border border-line bg-paper-2 px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40";

interface Props {
  userId: string;
  onCreated?: (sessionId: string) => void;
}

interface Country {
  code: string;
  name: string;
}

function extractCountries(tree: unknown): Country[] {
  if (!tree || typeof tree !== "object") return [];
  const t = tree as Record<string, unknown>;
  const countries = Array.isArray(t.countries) ? (t.countries as Country[]) : [];
  return countries
    .filter((c) => c && typeof c.code === "string" && typeof c.name === "string")
    .sort((a, b) => a.name.localeCompare(b.name, "it"));
}

export function NewSessionForm({ userId, onCreated }: Props) {
  const geoQuery = useGeoTree();
  const createSession = useCreateSession(userId);
  const suggestSkills = useSuggestSkillsForRole();
  const setSessionId = useAppState((s) => s.setSessionId);

  const [role, setRole] = useState("");
  const [country, setCountry] = useState("");
  const [location, setLocation] = useState("");
  const [contract, setContract] = useState("");
  const [threshold, setThreshold] = useState(50);

  const [draftSkills, setDraftSkills] = useState<string[]>([]);
  const [draftCompanies, setDraftCompanies] = useState<string[]>([]);
  const [newCompany, setNewCompany] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const countries = extractCountries(geoQuery.data);

  async function handleSuggest() {
    if (!role.trim()) {
      toast.warning("Scrivi prima il ruolo");
      return;
    }
    try {
      const items = await suggestSkills.mutateAsync({ role, limit: 12 });
      setSuggestions(items.map((i) => i.name));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore suggerimenti");
    }
  }

  function toggleSkill(name: string) {
    setDraftSkills((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name],
    );
  }

  function addCompany() {
    const trimmed = newCompany.trim();
    if (!trimmed) return;
    if (draftCompanies.some((c) => c.toLowerCase() === trimmed.toLowerCase())) return;
    setDraftCompanies((prev) => [...prev, trimmed]);
    setNewCompany("");
  }

  async function handleCreate() {
    if (!role.trim()) {
      toast.warning("Ruolo obbligatorio");
      return;
    }
    try {
      const created = await createSession.mutateAsync({
        role_title: role,
        preferred_country: country || null,
        location_pref: location || null,
        contract_type: contract || null,
        match_threshold: threshold / 100,
        hard_skills: draftSkills,
        companies: draftCompanies.map((name) => ({ name, source: "manual" })),
      });
      toast.success("Ricerca creata");
      setSessionId(created.id);
      onCreated?.(created.id);
      // Reset
      setRole("");
      setLocation("");
      setDraftSkills([]);
      setDraftCompanies([]);
      setSuggestions([]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore");
    }
  }

  return (
    <Card className="p-8">
      <header className="mb-6">
        <h2 className="font-serif text-2xl">Nuova ricerca</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Un ruolo, un paese. Le competenze e le aziende target si scelgono qui sotto.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-1.5 md:col-span-2">
          <Label>Ruolo</Label>
          <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Data Analyst" />
        </div>

        <div className="space-y-1.5">
          <Label>Paese</Label>
          <select
            className={selectClass}
            value={country}
            onChange={(e) => setCountry(e.target.value)}
          >
            <option value="">Nessuna preferenza</option>
            {countries.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <Label>Zona (facoltativa)</Label>
          <Input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Milano, Berlin…"
          />
        </div>

        <div className="space-y-1.5">
          <Label>Contratto</Label>
          <select
            className={selectClass}
            value={contract}
            onChange={(e) => setContract(e.target.value)}
          >
            {CONTRACTS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <Label>Soglia di compatibilità: {threshold}%</Label>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="w-full accent-accent"
          />
          <p className="text-xs text-ink-faint">
            Sotto questa soglia l'annuncio viene scartato ma finisce nel resoconto.
          </p>
        </div>
      </div>

      <div className="mt-8 space-y-4 border-t border-line pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-ink-faint">
              Competenze richieste
            </p>
            <p className="text-sm text-ink-soft">
              Cosa deve avere un candidato ideale per questo ruolo.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSuggest}
            disabled={suggestSkills.isPending}
          >
            Suggerisci competenze
          </Button>
        </div>

        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => {
              const isOn = draftSkills.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggleSkill(s)}
                  className={
                    "rounded-full border px-3 py-1 text-xs transition-colors " +
                    (isOn
                      ? "border-accent bg-accent text-paper"
                      : "border-line hover:border-accent hover:text-accent")
                  }
                >
                  {isOn ? "✓ " : "+ "}
                  {s}
                </button>
              );
            })}
          </div>
        )}

        {draftSkills.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {draftSkills.map((s) => (
              <Badge key={s} className="gap-1 pr-1">
                {s}
                <button
                  type="button"
                  onClick={() => toggleSkill(s)}
                  className="rounded-sm p-0.5 hover:bg-ink/10"
                  aria-label={`Rimuovi ${s}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="mt-8 space-y-4 border-t border-line pt-6">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-faint">
            Aziende target
          </p>
          <p className="text-sm text-ink-soft">
            Le careers page di queste aziende verranno scandagliate insieme ai portali.
          </p>
        </div>

        <div className="flex gap-2">
          <Input
            value={newCompany}
            onChange={(e) => setNewCompany(e.target.value)}
            placeholder="Nome azienda"
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCompany())}
          />
          <Button variant="outline" onClick={addCompany}>
            Aggiungi
          </Button>
        </div>

        {draftCompanies.length > 0 && (
          <ul className="space-y-1">
            {draftCompanies.map((c) => (
              <li
                key={c}
                className="flex items-center justify-between rounded-sm border border-line bg-paper-2 px-3 py-2 text-sm"
              >
                <span>{c}</span>
                <button
                  type="button"
                  onClick={() =>
                    setDraftCompanies((prev) => prev.filter((x) => x !== c))
                  }
                  className="rounded-sm p-1 text-ink-faint hover:bg-line/50 hover:text-bad"
                  aria-label={`Rimuovi ${c}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-8 flex flex-col items-end gap-2 border-t border-line pt-6">
        <Button size="lg" onClick={handleCreate} disabled={createSession.isPending}>
          Crea ricerca
        </Button>
        <p className="text-xs text-ink-faint">
          Salva solo questa configurazione — nel passo successivo trovi il bottone
          "Avvia ricerca" per far partire davvero la ricerca sui portali
        </p>
      </div>
    </Card>
  );
}
