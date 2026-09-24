import { useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAddHardSkill, useDeleteHardSkill, useHardSkills } from "@/api/queries";

const LEVELS = [
  ["beginner", "Base"],
  ["intermediate", "Intermedio"],
  ["expert", "Avanzato"],
] as const;

const VIA = [
  ["work", "Sul lavoro"],
  ["university", "Università"],
  ["self_taught", "Autodidatta"],
  ["certification", "Certificazione"],
] as const;

const selectClass =
  "h-9 rounded-sm border border-line bg-paper-2 px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40";

export function HardSkillsPanel({ userId }: { userId: string }) {
  const skillsQuery = useHardSkills(userId);
  const addSkill = useAddHardSkill(userId);
  const deleteSkill = useDeleteHardSkill(userId);

  const [name, setName] = useState("");
  const [level, setLevel] = useState<string>("intermediate");
  const [years, setYears] = useState<number>(1);
  const [via, setVia] = useState<string>("work");

  async function handleAdd() {
    if (!name.trim()) return;
    try {
      await addSkill.mutateAsync({ name, level, years_exp: years, acquired_via: via });
      setName("");
      toast.success("Skill aggiunta");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore aggiunta skill");
    }
  }

  return (
    <Card className="p-8">
      <header className="mb-4">
        <h2 className="font-serif text-2xl">Competenze tecniche</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Cosa sai fare, indipendentemente da dove l'hai imparato.
        </p>
      </header>

      <div className="grid grid-cols-1 items-end gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto_auto_auto]">
        <div className="space-y-1.5">
          <Label>Nome</Label>
          <Input
            placeholder="Python"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Livello</Label>
          <select
            className={selectClass}
            value={level}
            onChange={(e) => setLevel(e.target.value)}
          >
            {LEVELS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label>Anni</Label>
          <Input
            type="number"
            min={0}
            max={50}
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            className="w-20"
          />
        </div>
        <div className="space-y-1.5">
          <Label>Da dove</Label>
          <select className={selectClass} value={via} onChange={(e) => setVia(e.target.value)}>
            {VIA.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <Button variant="outline" onClick={handleAdd} disabled={addSkill.isPending}>
          Aggiungi
        </Button>
      </div>

      <ul className="mt-6 space-y-2">
        {(skillsQuery.data ?? []).map((s) => (
          <li
            key={s.id}
            className="flex items-center justify-between rounded-sm border border-line bg-paper-2 px-3 py-2 text-sm"
          >
            <span>
              <span className="font-medium">{s.name}</span>
              <span className="ml-2 text-ink-faint">
                {s.level} · {s.years_exp}y · {s.acquired_via}
              </span>
            </span>
            <button
              type="button"
              onClick={() => deleteSkill.mutate(s.id)}
              className="rounded-sm p-1 text-ink-faint hover:bg-line/50 hover:text-bad"
              aria-label={`Rimuovi ${s.name}`}
            >
              <X className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
