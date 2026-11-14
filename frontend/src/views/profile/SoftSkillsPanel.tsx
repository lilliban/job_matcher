import { useEffect, useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  useAddSoftSkill,
  useDeleteSoftSkill,
  useSoftSkills,
  useSoftSkillsCatalog,
  useSuggestSoftSkills,
} from "@/api/queries";
import type { SkillSuggestion } from "@/api/schemas";

interface Props {
  userId: string;
}

export function SoftSkillsPanel({ userId }: Props) {
  const catalogQuery = useSoftSkillsCatalog();
  const skillsQuery = useSoftSkills(userId);
  const addSkill = useAddSoftSkill(userId);
  const deleteSkill = useDeleteSoftSkill(userId);
  const suggestSimilar = useSuggestSoftSkills();

  const [similarFor, setSimilarFor] = useState<string | null>(null);
  const [similar, setSimilar] = useState<SkillSuggestion[]>([]);

  const selected = new Set((skillsQuery.data ?? []).map((s) => s.name.toLowerCase()));
  const idByName = new Map((skillsQuery.data ?? []).map((s) => [s.name.toLowerCase(), s.id]));

  useEffect(() => {
    setSimilarFor(null);
    setSimilar([]);
  }, [userId]);

  async function toggle(name: string) {
    const isOn = selected.has(name.toLowerCase());
    try {
      if (isOn) {
        const id = idByName.get(name.toLowerCase());
        if (id) await deleteSkill.mutateAsync(id);
      } else {
        await addSkill.mutateAsync({ name });
        // Suggerisci simili
        try {
          const sims = await suggestSimilar.mutateAsync({ skillName: name, limit: 6 });
          setSimilarFor(name);
          setSimilar(sims.filter((s) => !selected.has(s.name.toLowerCase())));
        } catch {
          /* ignora silenziosamente */
        }
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore soft skill");
    }
  }

  return (
    <Card className="p-8">
      <header className="mb-4">
        <h2 className="font-serif text-2xl">Soft skill</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Sono tue, non cambiano da un ruolo all'altro.
        </p>
      </header>

      {catalogQuery.isLoading ? (
        <div className="text-ink-faint">Carico il catalogo…</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {(catalogQuery.data ?? []).map((s) => {
            const isOn = selected.has(s.name.toLowerCase());
            return (
              <button
                key={s.name}
                type="button"
                onClick={() => toggle(s.name)}
                className={
                  "rounded-full border px-3 py-1 text-xs transition-colors " +
                  (isOn
                    ? "border-accent bg-accent text-paper"
                    : "border-line hover:border-accent hover:text-accent")
                }
              >
                {s.name}
              </button>
            );
          })}
        </div>
      )}

      {similarFor && similar.length > 0 && (
        <div className="mt-6 rounded-sm border border-accent-wash bg-accent-wash/40 p-4">
          <p className="mb-3 text-xs font-medium text-accent-ink">
            ✨ Simili a <span className="font-semibold">{similarFor}</span>
          </p>
          <div className="flex flex-wrap gap-2">
            {similar.map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => toggle(s.name)}
                className="rounded-full border border-accent bg-paper-2 px-3 py-1 text-xs hover:bg-accent hover:text-paper"
              >
                + {s.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {selected.size > 0 && (
        <div className="mt-6">
          <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-faint">
            Selezionate ({selected.size})
          </p>
          <div className="flex flex-wrap gap-2">
            {(skillsQuery.data ?? []).map((s) => (
              <Badge key={s.id} className="gap-1 pr-1">
                {s.name}
                <button
                  type="button"
                  onClick={() => deleteSkill.mutate(s.id)}
                  className="rounded-sm p-0.5 hover:bg-ink/10"
                  aria-label={`Rimuovi ${s.name}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
