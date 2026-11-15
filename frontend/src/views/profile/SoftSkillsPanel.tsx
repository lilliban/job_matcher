import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Check, Plus } from "lucide-react";

import { Card } from "@/components/ui/card";
import {
  useAddSoftSkill,
  useDeleteSoftSkill,
  useSoftSkills,
  useSoftSkillsCatalog,
  useSuggestSoftSkills,
} from "@/api/queries";
import type { SkillSuggestion } from "@/api/schemas";
import { canonicalSoftSkill, softSkillKey } from "@/lib/softSkills";
import { cn } from "@/lib/utils";

interface Props {
  userId: string;
}

const canonical = canonicalSoftSkill;
const keyOf = softSkillKey;

export function SoftSkillsPanel({ userId }: Props) {
  const catalogQuery = useSoftSkillsCatalog();
  const skillsQuery = useSoftSkills(userId);
  const addSkill = useAddSoftSkill(userId);
  const deleteSkill = useDeleteSoftSkill(userId);
  const suggestSimilar = useSuggestSoftSkills();

  const [similarFor, setSimilarFor] = useState<string | null>(null);
  const [similar, setSimilar] = useState<SkillSuggestion[]>([]);

  // chiave canonica → id di tutte le righe che la rappresentano
  const idsByKey = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const s of skillsQuery.data ?? []) {
      const k = keyOf(s.name);
      map.set(k, [...(map.get(k) ?? []), s.id]);
    }
    return map;
  }, [skillsQuery.data]);

  // Una sola lista: prima il catalogo, poi le skill tue che non ci sono.
  const chips = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    const push = (n: string) => {
      const k = keyOf(n);
      if (seen.has(k)) return;
      seen.add(k);
      out.push(canonical(n));
    };
    (catalogQuery.data ?? []).forEach((s) => push(s.name));
    (skillsQuery.data ?? []).forEach((s) => push(s.name));
    return out;
  }, [catalogQuery.data, skillsQuery.data]);

  const selectedCount = idsByKey.size;

  useEffect(() => {
    setSimilarFor(null);
    setSimilar([]);
  }, [userId]);

  async function toggle(name: string) {
    const ids = idsByKey.get(keyOf(name)) ?? [];
    try {
      if (ids.length > 0) {
        // Togliendola si tolgono anche i doppioni, altrimenti resterebbe accesa.
        for (const id of ids) await deleteSkill.mutateAsync(id);
      } else {
        await addSkill.mutateAsync({ name: canonical(name) });
        try {
          const sims = await suggestSimilar.mutateAsync({ skillName: name, limit: 6 });
          setSimilarFor(canonical(name));
          setSimilar(sims.filter((s) => !idsByKey.has(keyOf(s.name)) && keyOf(s.name) !== keyOf(name)));
        } catch {
          /* i suggerimenti sono facoltativi */
        }
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Non sono riuscito ad aggiornare le soft skill");
    }
  }

  const freshSimilar = similar.filter((s) => !idsByKey.has(keyOf(s.name)));

  return (
    <Card className="p-5 sm:p-8">
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="jm-h2">Soft skill</h2>
          <p className="mt-1 text-sm text-ink-soft">
            Sono tue, non cambiano da un ruolo all'altro. Tocca per aggiungere o togliere.
          </p>
        </div>
        <span className="font-mono text-xs text-ink-faint">{selectedCount} scelte</span>
      </header>

      {catalogQuery.isLoading || skillsQuery.isLoading ? (
        <p role="status" className="text-ink-soft">Carico le soft skill…</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {chips.map((name) => {
            const isOn = idsByKey.has(keyOf(name));
            return (
              <li key={name}>
                <button
                  type="button"
                  aria-pressed={isOn}
                  onClick={() => toggle(name)}
                  className={cn(
                    "jm-press inline-flex h-10 items-center gap-1.5 rounded-full border px-4 text-sm",
                    isOn
                      ? "border-accent bg-accent text-paper-2"
                      : "border-line-hard bg-paper-2 text-ink hover:border-accent",
                  )}
                >
                  {isOn ? <Check className="h-4 w-4" aria-hidden /> : <Plus className="h-4 w-4 text-ink-faint" aria-hidden />}
                  {name}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {similarFor && freshSimilar.length > 0 && (
        <div className="mt-6 rounded-xl bg-surface p-4">
          <p className="mb-3 text-sm text-ink">
            Simili a <span className="font-medium">{similarFor}</span>
          </p>
          <div className="flex flex-wrap gap-2">
            {freshSimilar.map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => toggle(s.name)}
                className="jm-press inline-flex h-10 items-center gap-1.5 rounded-full border border-line-hard bg-paper-2 px-4 text-sm hover:border-accent"
              >
                <Plus className="h-4 w-4 text-ink-faint" aria-hidden />
                {canonical(s.name)}
              </button>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
