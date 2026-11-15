import { useRef, useState } from "react";
import { toast } from "sonner";
import { Download, FileText, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useGenerateApplication, type ApplicationResult } from "@/api/queries";
import { useCurrentUser } from "@/hooks/useCurrentUser";

const DOC_LABEL: Record<string, string> = {
  cv: "CV su misura",
  cover_letter: "Lettera di presentazione",
};

const EXPORT_FORMATS = [
  { fmt: "pdf", label: "PDF" },
  { fmt: "docx", label: "DOCX" },
  { fmt: "md", label: "Markdown" },
  { fmt: "txt", label: "Testo" },
];

const MAX_FILES = 5;

async function downloadExport(content: string, fmt: string, name: string) {
  const res = await fetch("/api/applications/export", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Token":
        (import.meta.env.VITE_API_TOKEN as string | undefined) ?? "local-dev-token-2026",
    },
    body: JSON.stringify({ content, fmt, name }),
  });
  if (!res.ok) {
    toast.error("Export fallito");
    return;
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Pannello "da un link": vive dentro la pagina Ricerche, non ha una sezione sua. */
export function ApplyPanel() {
  const { userId, isBooting } = useCurrentUser();
  const generate = useGenerateApplication();
  const fileInput = useRef<HTMLInputElement>(null);

  const [url, setUrl] = useState("");
  const [jobText, setJobText] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [guidelines, setGuidelines] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [wantCv, setWantCv] = useState(true);
  const [wantLetter, setWantLetter] = useState(true);
  const [result, setResult] = useState<ApplicationResult | null>(null);
  const [runId, setRunId] = useState(0);

  if (isBooting) return <div className="text-ink-faint">Caricamento…</div>;

  const addFiles = (picked: FileList | null) => {
    if (!picked) return;
    const next = [...files, ...Array.from(picked)].slice(0, MAX_FILES);
    setFiles(next);
    if (fileInput.current) fileInput.current.value = "";
  };

  const canSubmit =
    !!userId &&
    (url.trim() !== "" || jobText.trim() !== "") &&
    (wantCv || wantLetter) &&
    !generate.isPending;

  const submit = () => {
    if (!userId) return;
    const fd = new FormData();
    fd.append("user_id", userId);
    if (url.trim()) fd.append("url", url.trim());
    if (jobText.trim()) fd.append("job_text", jobText.trim());
    if (guidelines.trim()) fd.append("guidelines", guidelines.trim());
    fd.append(
      "doc_types",
      [wantCv && "cv", wantLetter && "cover_letter"].filter(Boolean).join(","),
    );
    files.forEach((f) => fd.append("files", f));

    generate.mutate(fd, {
      onSuccess: (data) => {
        setResult(data);
        setRunId((n) => n + 1); // azzera le modifiche manuali della generazione precedente
      },
      onError: (err) => {
        toast.error(err.message);
        // pagina non scaricabile → apro subito il campo "incolla il testo"
        if (/incolla/i.test(err.message)) setShowPaste(true);
      },
    });
  };

  return (
    <div>

      {!userId ? (
        <Card className="p-8 text-ink-soft">Crea prima il tuo profilo.</Card>
      ) : (
        <Card className="space-y-6 p-6">
          <div className="space-y-2">
            <Label htmlFor="apply-url">Link dell'annuncio</Label>
            <Input
              id="apply-url"
              type="url"
              placeholder="https://azienda.com/careers/sviluppatore-python"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <button
              type="button"
              className="text-xs text-ink-soft underline underline-offset-2"
              onClick={() => setShowPaste((v) => !v)}
            >
              {showPaste ? "Nascondi" : "Il link non funziona? Incolla il testo dell'annuncio"}
            </button>
            {showPaste && (
              <Textarea
                rows={6}
                placeholder="Incolla qui il testo dell'annuncio (ha la precedenza sul link)"
                value={jobText}
                onChange={(e) => setJobText(e.target.value)}
              />
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="apply-guidelines">Linee guida e schema</Label>
            <Textarea
              id="apply-guidelines"
              rows={7}
              placeholder={
                "Esempi:\n- CV di una pagina, sezioni: Profilo, Competenze, Esperienze, Formazione\n- Lettera in 3 paragrafi, tono diretto, max 250 parole\n- Metti in evidenza i progetti open source"
              }
              value={guidelines}
              onChange={(e) => setGuidelines(e.target.value)}
            />
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInput}
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md"
                className="hidden"
                onChange={(e) => addFiles(e.target.files)}
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={files.length >= MAX_FILES}
                onClick={() => fileInput.current?.click()}
              >
                <FileText className="mr-1 h-4 w-4" /> Aggiungi file (PDF, DOCX, TXT, MD)
              </Button>
              {files.map((f, i) => (
                <span
                  key={`${f.name}-${i}`}
                  className="inline-flex items-center gap-1 rounded-full border border-line bg-paper py-1 pl-3 pr-1 text-xs"
                >
                  {f.name}
                  <button
                    type="button"
                    aria-label={`Rimuovi ${f.name}`}
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={wantCv} onChange={(e) => setWantCv(e.target.checked)} />
              CV
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={wantLetter}
                onChange={(e) => setWantLetter(e.target.checked)}
              />
              Lettera di presentazione
            </label>
            <Button className="ml-auto" disabled={!canSubmit} onClick={submit}>
              {generate.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Scrivo…
                </>
              ) : (
                "Genera"
              )}
            </Button>
          </div>
        </Card>
      )}

      {result && <ResultPanel key={runId} result={result} />}
    </div>
  );
}

function ResultPanel({ result }: { result: ApplicationResult }) {
  const { listing } = result;
  const stem = (listing.company_name || "candidatura").trim().replace(/\s+/g, "_");
  // Stato locale: l'utente può correggere il testo prima di esportare.
  const [edited, setEdited] = useState<Record<string, string>>(
    result.documents as Record<string, string>,
  );

  return (
    <section className="mt-10 space-y-6">
      <div>
        <p className="text-xs font-medium text-ink-faint">
          Annuncio riconosciuto
        </p>
        <h2 className="jm-h2">
          {listing.title}
          {listing.company_name ? ` — ${listing.company_name}` : ""}
        </h2>
        {listing.location && <p className="text-sm text-ink-soft">{listing.location}</p>}
      </div>

      {Object.keys(edited).map((docType) => (
        <Card key={docType} className="overflow-hidden">
          <header className="border-b border-line p-4">
            <h3 className="jm-h2">{DOC_LABEL[docType] ?? docType}</h3>
          </header>
          <Textarea
            className="min-h-[360px] rounded-none border-0 font-mono"
            value={edited[docType]}
            onChange={(e) => setEdited({ ...edited, [docType]: e.target.value })}
          />
          <footer className="flex flex-wrap gap-2 border-t border-line bg-paper p-3">
            {EXPORT_FORMATS.map((f) => (
              <Button
                key={f.fmt}
                size="sm"
                variant="outline"
                onClick={() => downloadExport(edited[docType], f.fmt, `${docType}_${stem}`)}
              >
                <Download className="mr-1 h-3 w-3" /> {f.label}
              </Button>
            ))}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                navigator.clipboard.writeText(edited[docType]);
                toast.success("Testo copiato");
              }}
            >
              Copia testo
            </Button>
          </footer>
        </Card>
      ))}

      {result.llm_model && (
        <p className="font-mono text-xs text-ink-faint">Modello: {result.llm_model}</p>
      )}
    </section>
  );
}
