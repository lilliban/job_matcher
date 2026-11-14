import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, RefreshCw, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useAddHardSkill,
  useDeleteHardSkill,
  useExperiences,
  useHardSkills,
  useSimilarHardSkills,
  useSkillAdvice,
  type SkillAdvice,
} from "@/api/queries";

const LEVELS = [
  ["beginner", "Base"],
  ["intermediate", "Intermedio"],
  ["expert", "Avanzato"],
] as const;

const LEVEL_LABEL: Record<string, string> = Object.fromEntries(LEVELS);

const selectClass =
  "h-9 rounded-sm border border-line bg-paper-2 px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40";

export function HardSkillsPanel({ userId }: { userId: string }) {
  const skillsQuery = useHardSkills(userId);
  const experiences = useExperiences(userId);
  const addSkill = useAddHardSkill(userId);
  const deleteSkill = useDeleteHardSkill(userId);
  const similarMut = useSimilarHardSkills(userId);
  // Il suggerimento dipende da cosa HAI FATTO (esperienze), non da quante
  // skill hai già: altrimenti ogni aggiunta rifarebbe la chiamata all'AI.
  const advice = useSkillAdvice(userId, String(experiences.data?.length ?? 0));

  const [name, setName] = useState("");
  const [level, setLevel] = useState<string>("intermediate");
  const [years, setYears] = useState<number>(1);
  const [showDetails, setShowDetails] = useState(false);
  const [similarFor, setSimilarFor] = useState<string | null>(null);
  const [similar, setSimilar] = useState<SkillAdvice[]>([]);

  const skills = skillsQuery.data ?? [];
  const owned = new Set(skills.map((s) => s.name.toLowerCase()));

  async function add(skillName: string, opts?: { fromSuggestion?: boolean }) {
    const clean = skillName.trim();
    if (!clean || owned.has(clean.toLowerCase())) return;
    try {
      await addSkill.mutateAsync({
        name: clean,
        level: opts?.fromSuggestion ? "intermediate" : level,
        years_exp: opts?.fromSuggestion ? 1 : years,
        acquired_via: "work",
      });
      setName("");
      // subito dopo l'aggiunta: le competenze che di solito vanno insieme
      setSimilarFor(clean);
      setSimilar([]);
      similarMut.mutate(clean, {
        onSuccess: (r) => setSimilar(r.skills),
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore aggiunta competenza");
    }
  }

  const suggestions = (advice.data?.skills ?? []).filter((s) => !owned.has(s.name.toLowerCase()));

  return (
    <Card className="p-8">
      <header className="mb-5">
        <h2 className="font-serif text-2xl">Competenze tecniche</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Strumenti, linguaggi, metodi: tutto ciò che sai usare, anche se ti sembra scontato.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[220px] flex-1">
          <Input
            placeholder="Scrivi una competenza e premi Invio (es. Python)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add(name)}
            aria-label="Nuova competenza"
          />
        </div>
        <Button variant="outline" onClick={() => add(name)} disabled={!name.trim() || addSkill.isPending}>
          <Plus className="mr-1 h-4 w-4" /> Aggiungi
        </Button>
        <button
          type="button"
          className="text-xs text-ink-soft underline underline-offset-2"
          onClick={() => setShowDetails((v) => !v)}
        >
          {showDetails ? "Nascondi dettagli" : "Livello e anni"}
        </button>
      </div>

      {showDetails && (
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <span className="text-ink-soft">Per la prossima che aggiungi:</span>
          <select className={selectClass} value={level} onChange={(e) => setLevel(e.target.value)} aria-label="Livello">
            {LEVELS.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
          <label className="flex items-center gap-2">
            Anni
            <Input type="number" min={0} max={50} value={years} onChange={(e) => setYears(Number(e.target.value))} className="w-20" />
          </label>
        </div>
      )}

      {similarFor && (similarMut.isPending || similar.length > 0) && (
        <Suggestions
          title={<>Chi sa <strong>{similarFor}</strong> spesso conosce anche</>}
          loading={similarMut.isPending}
          items={similar.filter((s) => !owned.has(s.name.toLowerCase()))}
          onPick={(n) => add(n, { fromSuggestion: true })}
          onClose={() => setSimilarFor(null)}
        />
      )}

      {skills.length > 0 && (
        <ul className="mt-6 flex flex-wrap gap-2">
          {skills.map((s) => (
            <li
              key={s.id}
              className="group flex items-center gap-2 rounded-full border border-line bg-paper-2 py-1 pl-3 pr-1 text-sm"
            >
              <span className="font-medium">{s.name}</span>
              <span className="text-xs text-ink-faint">
                {LEVEL_LABEL[s.level ?? ""] ?? s.level}
                {s.years_exp ? ` · ${s.years_exp}a` : ""}
              </span>
              <button
                type="button"
                onClick={() => deleteSkill.mutate(s.id)}
                className="rounded-full p-1 text-ink-faint hover:bg-bad-wash hover:text-bad"
                aria-label={`Rimuovi ${s.name}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6 rounded-sm border border-accent-wash bg-accent-wash/40 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="flex items-center gap-2 text-sm font-medium text-accent-ink">
            <Sparkles className="h-4 w-4" /> Forse hai anche queste competenze
          </p>
          <button
            type="button"
            className="flex items-center gap-1 text-xs text-ink-soft hover:text-ink"
            onClick={() => advice.refetch()}
            disabled={advice.isFetching}
          >
            <RefreshCw className={"h-3 w-3 " + (advice.isFetching ? "animate-spin" : "")} /> Altre idee
          </button>
        </div>
        {advice.isLoading || advice.isFetching ? (
          <p className="flex items-center gap-2 text-sm text-ink-soft">
            <Loader2 className="h-4 w-4 animate-spin" /> Guardo il tuo profilo…
          </p>
        ) : suggestions.length === 0 ? (
          <p className="text-sm text-ink-soft">
            {skills.length === 0 && (experiences.data?.length ?? 0) === 0
              ? "Aggiungi un'esperienza o qualche competenza e ti darò dei suggerimenti."
              : "Nessun suggerimento al momento."}
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s.name}
                type="button"
                title={s.why}
                onClick={() => add(s.name, { fromSuggestion: true })}
                className="rounded-full border border-accent bg-paper-2 px-3 py-1 text-xs hover:bg-accent hover:text-paper"
              >
                + {s.name}
              </button>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-ink-faint">
          Sono compatibili col tuo percorso e compaiono spesso negli annunci. Aggiungi solo quelle
          che sai davvero usare.
        </p>
      </div>
    </Card>
  );
}

function Suggestions({
  title, items, loading, onPick, onClose,
}: {
  title: React.ReactNode; items: SkillAdvice[]; loading: boolean;
  onPick: (name: string) => void; onClose: () => void;
}) {
  return (
    <div className="mt-4 rounded-sm border border-accent-wash bg-accent-wash/40 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <p className="text-sm text-accent-ink">✨ {title}</p>
        <button type="button" onClick={onClose} aria-label="Chiudi suggerimenti" className="text-ink-faint hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </div>
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-ink-soft">
          <Loader2 className="h-4 w-4 animate-spin" /> Cerco competenze collegate…
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {items.map((s) => (
            <button
              key={s.name}
              type="button"
              onClick={() => onPick(s.name)}
              className="rounded-full border border-accent bg-paper-2 px-3 py-1 text-xs hover:bg-accent hover:text-paper"
            >
              + {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
