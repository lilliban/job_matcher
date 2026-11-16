import { useState } from "react";
import { toast } from "sonner";
import { Download, Eye } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useMatchDocuments } from "@/api/queries";
import type { GeneratedDocumentOut } from "@/api/schemas";

/** Nome accessibile del pulsante che apre il documento. */
const DOC_OPEN_LABEL: Record<string, string> = {
  cv: "Apri CV su misura",
  cover_letter: "Apri lettera",
  email: "Apri email",
};

const DOC_LABEL: Record<string, string> = {
  cv: "CV su misura",
  cover_letter: "Lettera",
  email: "Email",
};

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
  const [openDoc, setOpenDoc] = useState<GeneratedDocumentOut | null>(null);

  if (docs.isLoading) return <div className="text-xs text-ink-faint">Carico documenti…</div>;
  if (!docs.data || docs.data.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-line p-4 text-sm text-ink-faint">
        Nessun documento ancora. «Prepara CV e lettera» li crea.
      </div>
    );
  }

  return (
    <div>
      <p className="mb-2 text-xs font-medium text-ink-faint">
        Documenti generati
      </p>
      <ul className="space-y-2">
        {docs.data.map((d) => (
          <li
            key={d.id}
            className="flex items-center justify-between rounded-xl border border-line bg-paper-2 py-1 pl-4 pr-1 text-sm"
          >
            <span className="font-medium">{DOC_LABEL[d.doc_type] ?? "Documento"}</span>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setOpenDoc(d)}
                aria-label={DOC_OPEN_LABEL[d.doc_type] ?? "Apri documento"}
                title={DOC_OPEN_LABEL[d.doc_type] ?? "Apri documento"}
              >
                <Eye className="h-4 w-4" aria-hidden />
              </Button>
            </div>
          </li>
        ))}
      </ul>

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
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 p-4 sm:items-center"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-line bg-paper"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line p-4">
          <h3 className="jm-h2">{DOC_LABEL[doc.doc_type] ?? "Documento"}</h3>
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
