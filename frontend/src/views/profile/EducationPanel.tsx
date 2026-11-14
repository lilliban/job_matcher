import { useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAddEducation, useDeleteEducation, useEducation } from "@/api/queries";

const emptyEdu = { institution: "", degree: "", field: "", year: "" };

export function EducationPanel({ userId }: { userId: string }) {
  const listQuery = useEducation(userId);
  const addEdu = useAddEducation(userId);
  const deleteEdu = useDeleteEducation(userId);

  const [form, setForm] = useState(emptyEdu);
  const update = <K extends keyof typeof form>(k: K, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));

  async function handleAdd() {
    if (!form.institution.trim() || !form.degree.trim()) {
      toast.warning("Istituto e titolo obbligatori");
      return;
    }
    try {
      await addEdu.mutateAsync({
        institution: form.institution,
        degree: form.degree,
        field: form.field || null,
        year: form.year || null,
      });
      setForm(emptyEdu);
      toast.success("Titolo aggiunto");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore");
    }
  }

  return (
    <Card className="p-8">
      <header className="mb-4">
        <h2 className="font-serif text-2xl">Formazione</h2>
      </header>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Istituto</Label>
          <Input
            value={form.institution}
            onChange={(e) => update("institution", e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Titolo</Label>
          <Input value={form.degree} onChange={(e) => update("degree", e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Ambito</Label>
          <Input value={form.field} onChange={(e) => update("field", e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Anno</Label>
          <Input value={form.year} onChange={(e) => update("year", e.target.value)} />
        </div>
      </div>

      <div className="mt-4 flex justify-end">
        <Button variant="outline" onClick={handleAdd} disabled={addEdu.isPending}>
          Aggiungi titolo
        </Button>
      </div>

      <ul className="mt-6 space-y-2">
        {(listQuery.data ?? []).map((e) => (
          <li
            key={e.id}
            className="flex items-center justify-between rounded-sm border border-line bg-paper-2 px-3 py-2 text-sm"
          >
            <span>
              <span className="font-medium">{e.degree}</span>
              <span className="ml-2 text-ink-soft">{e.institution}</span>
              {e.field && <span className="ml-2 text-ink-faint">· {e.field}</span>}
              {e.year && <span className="ml-2 text-ink-faint">· {e.year}</span>}
            </span>
            <button
              type="button"
              onClick={() => deleteEdu.mutate(e.id)}
              className="rounded-sm p-1 text-ink-faint hover:bg-line/50 hover:text-bad"
              aria-label="Rimuovi titolo"
            >
              <X className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
