import { useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useAddLanguage, useDeleteLanguage, useLanguages } from "@/api/queries";

const LANGUAGES = [
  ["italian", "Italiano"],
  ["english", "Inglese"],
  ["german", "Tedesco"],
  ["french", "Francese"],
  ["spanish", "Spagnolo"],
  ["portuguese", "Portoghese"],
  ["dutch", "Olandese"],
] as const;

const LEVELS = [
  ["madrelingua", "Madrelingua"],
  ["A1", "A1 - Base"],
  ["A2", "A2 - Elementare"],
  ["B1", "B1 - Intermedio"],
  ["B2", "B2 - Intermedio-alto"],
  ["C1", "C1 - Avanzato"],
  ["C2", "C2 - Padronanza"],
] as const;

const selectClass =
  "h-9 rounded-sm border border-line bg-paper-2 px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40";

export function LanguagesPanel({ userId }: { userId: string }) {
  const languagesQuery = useLanguages(userId);
  const addLang = useAddLanguage(userId);
  const deleteLang = useDeleteLanguage(userId);

  const [language, setLanguage] = useState<string>("italian");
  const [level, setLevel] = useState<string>("madrelingua");

  async function handleAdd() {
    try {
      await addLang.mutateAsync({ language, level, is_native: level === "madrelingua" });
      toast.success("Lingua aggiunta");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore aggiunta lingua");
    }
  }

  return (
    <Card className="p-8">
      <header className="mb-4">
        <h2 className="font-serif text-2xl">Lingue conosciute</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Servono per filtrare gli annunci che richiedono lingue che non parli.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label>Lingua</Label>
          <select
            className={selectClass}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            {LANGUAGES.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
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
        <Button variant="outline" onClick={handleAdd} disabled={addLang.isPending}>
          Aggiungi
        </Button>
      </div>

      <ul className="mt-6 space-y-2">
        {(languagesQuery.data ?? []).map((l) => (
          <li
            key={l.id}
            className="flex items-center justify-between rounded-sm border border-line bg-paper-2 px-3 py-2 text-sm"
          >
            <span>
              <span className="font-medium capitalize">{l.language}</span>
              <span className="ml-2 text-ink-faint">{l.level}</span>
            </span>
            <button
              type="button"
              onClick={() => deleteLang.mutate(l.id)}
              className="rounded-sm p-1 text-ink-faint hover:bg-line/50 hover:text-bad"
              aria-label="Rimuovi"
            >
              <X className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
