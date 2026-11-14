import { useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAddExperience, useDeleteExperience, useExperiences } from "@/api/queries";

const emptyExp = {
  company: "",
  role: "",
  start_date: "",
  end_date: "",
  description: "",
  skills_used: "",
};

export function ExperiencesPanel({ userId }: { userId: string }) {
  const listQuery = useExperiences(userId);
  const addExp = useAddExperience(userId);
  const deleteExp = useDeleteExperience(userId);

  const [form, setForm] = useState(emptyExp);

  const update = <K extends keyof typeof form>(k: K, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));

  async function handleAdd() {
    if (!form.company.trim() || !form.role.trim()) {
      toast.warning("Azienda e ruolo sono obbligatori");
      return;
    }
    try {
      await addExp.mutateAsync({
        company: form.company,
        role: form.role,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        description: form.description || null,
        skills_used: form.skills_used || null,
      });
      setForm(emptyExp);
      toast.success("Esperienza aggiunta");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore");
    }
  }

  return (
    <Card className="p-8">
      <header className="mb-4">
        <h2 className="font-serif text-2xl">Esperienze</h2>
      </header>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Azienda</Label>
          <Input value={form.company} onChange={(e) => update("company", e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Ruolo</Label>
          <Input value={form.role} onChange={(e) => update("role", e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Da</Label>
          <Input
            value={form.start_date}
            onChange={(e) => update("start_date", e.target.value)}
            placeholder="03/2023"
          />
        </div>
        <div className="space-y-1.5">
          <Label>A</Label>
          <Input
            value={form.end_date}
            onChange={(e) => update("end_date", e.target.value)}
            placeholder="in corso"
          />
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label>Cosa facevi</Label>
          <Textarea
            rows={2}
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
          />
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label>Tecnologie usate</Label>
          <Input
            value={form.skills_used}
            onChange={(e) => update("skills_used", e.target.value)}
            placeholder="PHP, Yii, MySQL"
          />
        </div>
      </div>

      <div className="mt-4 flex justify-end">
        <Button variant="outline" onClick={handleAdd} disabled={addExp.isPending}>
          Aggiungi esperienza
        </Button>
      </div>

      <ul className="mt-6 space-y-3">
        {(listQuery.data ?? []).map((e) => (
          <li
            key={e.id}
            className="flex items-start justify-between gap-3 rounded-sm border border-line bg-paper-2 p-3 text-sm"
          >
            <div>
              <div className="font-medium">
                {e.role} · <span className="text-ink-soft">{e.company}</span>
              </div>
              <div className="mt-0.5 text-xs text-ink-faint">
                {e.start_date} — {e.end_date || "in corso"}
              </div>
              {e.description && <p className="mt-1 text-ink-soft">{e.description}</p>}
            </div>
            <button
              type="button"
              onClick={() => deleteExp.mutate(e.id)}
              className="rounded-sm p-1 text-ink-faint hover:bg-line/50 hover:text-bad"
              aria-label="Rimuovi esperienza"
            >
              <X className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
