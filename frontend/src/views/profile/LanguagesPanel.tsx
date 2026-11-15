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

/**
 * Nome italiano di una lingua salvata. Il valore può arrivare dal modulo
 * ("italian"), dal CV importato ("Italian") o come codice ISO ("it"):
 * si confronta in minuscolo e, se non è noto, si mostra com'è.
 */
const LANGUAGE_NAME: Record<string, string> = {
  ...Object.fromEntries(LANGUAGES),
  it: "Italiano",
  en: "Inglese",
  de: "Tedesco",
  fr: "Francese",
  es: "Spagnolo",
  pt: "Portoghese",
  nl: "Olandese",
  italiano: "Italiano",
  inglese: "Inglese",
  tedesco: "Tedesco",
  francese: "Francese",
  spagnolo: "Spagnolo",
  portoghese: "Portoghese",
  olandese: "Olandese",
};

function languageName(value: string): string {
  return LANGUAGE_NAME[value.trim().toLowerCase()] ?? value;
}

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
  "h-11 rounded-xl border border-field bg-paper-2 px-3 text-sm sm:h-10";

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
    <Card className="p-5 sm:p-8">
      <header className="mb-4">
        <h2 className="jm-h2">Lingue conosciute</h2>
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
            className="flex items-center justify-between rounded-xl border border-line bg-paper-2 py-1 pl-4 pr-1 text-sm"
          >
            <span>
              <span className="font-medium capitalize">{languageName(l.language)}</span>
              <span className="ml-2 text-ink-faint">{l.level}</span>
            </span>
            <button
              type="button"
              onClick={() => deleteLang.mutate(l.id)}
              className="jm-press grid h-10 w-10 shrink-0 place-items-center rounded-full text-ink-faint hover:bg-bad-wash hover:text-bad"
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
