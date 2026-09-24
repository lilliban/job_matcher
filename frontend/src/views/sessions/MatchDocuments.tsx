import { useState } from "react";
import { toast } from "sonner";
import { Download, Eye, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useMatchDocuments, useRegenerateDocument } from "@/api/queries";
import type { GeneratedDocumentOut } from "@/api/schemas";

const DOC_LABEL: Record<string, string> = {
  cv: "CV su misura",
  cover_letter: "Lettera",
  email: "Email",
};

const DOC_TYPES = Object.keys(DOC_LABEL);

const EXPORT_FORMATS: Array<{ fmt: string; label: string }> = [
  { fmt: "pdf", label: "PDF" },
  { fmt: "docx", label: "DOCX" },
  { fmt: "md", label: "Markdown" },
  { fmt: "txt", label: "Testo" },
];

async function downloadDocument(docId: string, fmt: string, filename: string) {
  const res = await fetch(`/api/documents/${docId}/export?fmt=${fmt}`, {
    headers: {
      "X-API-Token":
        (import.meta.env.VITE_API_TOKEN as string | undefined) ?? "local-dev-token-2026",
    },
  });
  if (!res.ok) {
    toast.error("Export fallito");
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function MatchDocuments({ matchId }: { matchId: string }) {
  const docs = useMatchDocuments(matchId);
  const regenerate = useRegenerateDocument(matchId);
  const [openDoc, setOpenDoc] = useState<GeneratedDocumentOut | null>(null);
  const [pendingType, setPendingType] = useState<string | null>(null);

  if (docs.isLoading) return <div className="text-xs text-ink-faint">Carico documenti…</div>;

  const existing = docs.data ?? [];
  const existingTypes = new Set(existing.map((d) => d.doc_type));
  const missingTypes = DOC_TYPES.filter((t) => !existingTypes.has(t));

  async function generate(docType: string) {
    setPendingType(docType);
    try {
      await regenerate.mutateAsync({ doc_type: docType });
      toast.success(`${DOC_LABEL[docType] ?? docType} generato`);
    } catch {
      toast.error("Generazione fallita");
    } finally {
      setPendingType(null);
    }
  }

  return (
    <div>
      {existing.length > 0 && (
        <>
          <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-faint">
            Documenti generati
          </p>
          <ul className="mb-3 space-y-2">
            {existing.map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between rounded-sm border border-line bg-paper-2 px-3 py-2 text-sm"
              >
                <div>
                  <span className="font-medium">{DOC_LABEL[d.doc_type] ?? d.doc_type}</span>
                  <Badge variant="outline" className="ml-2">
                    {d.doc_type}
                  </Badge>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => setOpenDoc(d)}>
                    <Eye className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={pendingType === d.doc_type}
                    onClick={() => generate(d.doc_type)}
                  >
                    <Sparkles className="h-4 w-4" />
                    {pendingType === d.doc_type ? "…" : "Rigenera"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {missingTypes.length > 0 && (
        <div className="rounded border border-dashed border-line p-3">
          {existing.length === 0 && (
            <p className="mb-2 text-sm text-ink-faint">
              Nessun documento ancora generato per questo match. Generali solo
              quando ti servono, per non consumare quota LLM inutilmente.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {missingTypes.map((t) => (
              <Button
                key={t}
                size="sm"
                variant="outline"
                disabled={pendingType === t}
                onClick={() => generate(t)}
              >
                <Sparkles className="mr-1 h-4 w-4" />
                {pendingType === t ? "Genero…" : `Genera ${DOC_LABEL[t] ?? t}`}
              </Button>
            ))}
          </div>
        </div>
      )}

      {openDoc && (
        <DocumentViewer
          doc={openDoc}
          onClose={() => setOpenDoc(null)}
        />
      )}
    </div>
  );
}

function DocumentViewer({
  doc,
  onClose,
}: {
  doc: GeneratedDocumentOut;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-4 sm:items-center"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded border border-line bg-paper shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line p-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-ink-faint">
              {doc.doc_type}
            </p>
            <h3 className="font-serif text-xl">{DOC_LABEL[doc.doc_type] ?? doc.doc_type}</h3>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Chiudi
          </Button>
        </header>

        <pre className="flex-1 overflow-y-auto whitespace-pre-wrap p-6 font-mono text-sm text-ink">
          {doc.content}
        </pre>

        <footer className="flex flex-wrap gap-2 border-t border-line bg-paper-2 p-3">
          {EXPORT_FORMATS.map((f) => (
            <Button
              key={f.fmt}
              size="sm"
              variant="outline"
              onClick={() => downloadDocument(doc.id, f.fmt, `documento-${doc.doc_type}`)}
            >
              <Download className="mr-1 h-3 w-3" /> {f.label}
            </Button>
          ))}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              navigator.clipboard.writeText(doc.content ?? "");
              toast.success("Testo copiato");
            }}
          >
            Copia testo
          </Button>
        </footer>
      </div>
    </div>
  );
}
