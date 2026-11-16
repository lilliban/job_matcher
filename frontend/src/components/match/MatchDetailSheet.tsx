import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUpRight, Bookmark, Check, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MatchDocuments } from "@/views/sessions/MatchDocuments";

import { StatusMenu } from "./StatusMenu";
import { BelowTag, CoverageBar, LowDataTag, SkillRow } from "./parts";
import {
  CATEGORY_LABEL,
  dateLabel,
  isLowData,
  isTracked,
  regionLabel,
  skillsBasis,
  type MatchView,
} from "./matchModel";
import { useMatchActions } from "./useMatchActions";

/** Indirizzo della scheda "Da un link", con l'annuncio già indicato e la candidatura a cui agganciare i documenti. */
export function prepareHref(sourceUrl: string | null, matchId: string): string {
  const params = new URLSearchParams({ scheda: "link", match: matchId });
  if (sourceUrl) params.set("url", sourceUrl);
  return `/ricerche?${params.toString()}`;
}

const DATE_PREFIX = { seen: "Visto il", saved: "Salvato il", found: "Trovato il" } as const;

/** Il testo di un annuncio in blocchi: gli annunci del feed separano ogni riga con una riga vuota. */
function paragraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((b) => b.replace(/[ \t]+$/gm, "").trim())
    .filter(Boolean);
}

/**
 * Il dettaglio di un annuncio, lo stesso per "I tuoi match", "Ricerche fatte" e
 * "Candidature". In alto il perché (percentuale, N di M skill, quelle che hai e
 * quelle che ti mancano), al centro la descrizione, in fondo le azioni che non
 * scorrono: Salva, Prepara CV e lettera, Apri l'annuncio e lo stato.
 *
 * Sotto i 640px è un pannello a tutto schermo con la chiusura in alto a destra;
 * sopra, un pannello laterale.
 */
export function MatchDetailSheet({ view, onClose }: { view: MatchView | null; onClose: () => void }) {
  return (
    <Dialog.Root open={!!view} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="jm-overlay fixed inset-0 z-40 bg-ink/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="jm-sheet fixed inset-0 z-50 flex h-dvh w-full flex-col bg-paper font-sans text-ink focus:outline-none sm:left-auto sm:max-w-lg sm:border-l sm:border-line"
        >
          {view && <SheetBody view={view} onClose={onClose} />}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function SheetBody({ view, onClose }: { view: MatchView; onClose: () => void }) {
  const navigate = useNavigate();
  const { ensureSaved, save, setStatus, isSaving } = useMatchActions();
  // Lo stato scelto appare subito nel menu; poi lo conferma il server.
  const [pending, setPending] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);

  // Cambiando annuncio (o a dati aggiornati) il valore provvisorio non vale più.
  useEffect(() => setPending(null), [view.key, view.status]);

  const saved = isTracked(view.status);
  const status = pending ?? view.status;
  const low = isLowData(view);
  const date = dateLabel(view.date);
  const place = regionLabel(view.region);

  async function changeStatus(next: string) {
    setPending(next);
    const ok = await setStatus(view, next);
    if (!ok) setPending(null);
  }

  async function prepare() {
    setPreparing(true);
    const id = await ensureSaved(view);
    setPreparing(false);
    if (!id) return;
    onClose();
    navigate(prepareHref(view.sourceUrl, id));
  }

  return (
    <>
      <header className="flex items-start justify-between gap-3 px-5 pb-3 pt-[max(1rem,env(safe-area-inset-top))] sm:px-8 sm:pt-6">
        <div className="min-w-0">
          <Dialog.Title className="text-2xl font-medium leading-tight tracking-[-0.02em] [overflow-wrap:anywhere]">
            {view.title}
          </Dialog.Title>
          <p className="mt-1.5 text-[15px] text-ink-soft [overflow-wrap:anywhere]">
            {view.company ?? "Azienda non indicata"} · {place}
          </p>
          <p className="mt-0.5 text-sm text-ink-faint">
            {[
              view.category && CATEGORY_LABEL[view.category],
              view.kind === "thesis" && "Tesi o dottorato",
              date && `${DATE_PREFIX[view.dateKind]} ${date}`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <Dialog.Close
          aria-label="Chiudi dettaglio"
          className="jm-press -mr-2 -mt-1 grid h-11 w-11 shrink-0 place-items-center rounded-full text-ink-soft hover:bg-surface"
        >
          <X className="h-5 w-5" aria-hidden />
        </Dialog.Close>
      </header>

      <div className="flex-1 overflow-y-auto overscroll-contain px-5 pb-6 sm:px-8">
        {/* Il perché */}
        <section aria-label="Perché è un match" className="border-y border-line py-5">
          <CoverageBar m={view} size="lg" />
          {view.coverage != null && (
            <p className="mt-2 text-sm text-ink-soft">
              Hai <span className="font-medium text-ink">{skillsBasis(view)}</span> tra quelle citate nell'annuncio.
              {low && " Con così pochi dati la percentuale è indicativa."}
            </p>
          )}
          {(view.belowThreshold || low) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {view.belowThreshold && <BelowTag />}
              {low && <LowDataTag />}
            </div>
          )}

          <dl className="mt-5 space-y-4">
            <SkillRow label="Hai" skills={view.have} tone="have" />
            <SkillRow label="Ti mancano" skills={view.missingRequired} tone="missing" />
            <SkillRow label="Gradite, non le hai" skills={view.missingNice} tone="nice" />
          </dl>
        </section>

        {/* La descrizione */}
        <section aria-label="Descrizione dell'annuncio" className="py-5">
          <h3 className="mb-2 text-sm font-medium text-ink-soft">Descrizione dell'annuncio</h3>
          {view.description ? (
            <div className="max-w-[68ch] space-y-3 text-[15px] leading-relaxed [overflow-wrap:anywhere]">
              {paragraphs(view.description).map((block, i) => (
                <p key={i} className="whitespace-pre-line">
                  {block}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-[15px] text-ink-soft">
              Il testo dell'annuncio non è disponibile qui.
              {view.sourceUrl && " Lo trovi sul sito: «Apri l'annuncio»."}
            </p>
          )}
        </section>

        {view.matchId && (
          <section aria-label="Documenti" className="pb-5">
            <MatchDocuments matchId={view.matchId} />
          </section>
        )}

        {view.pertinenza != null && (
          <section aria-label="Pertinenza della ricerca" className="border-t border-line py-5 text-sm text-ink-soft">
            <p>
              <span className="font-medium text-ink">Pertinenza {Math.round(view.pertinenza * 100)}%.</span> È il
              punteggio che la ricerca ha dato all'annuncio, non la copertura delle tue skill.
              {view.pertinenzaUniform &&
                " In questa ricerca è uguale per tutti gli annunci, quindi non aiuta a sceglierli: guarda la percentuale in alto."}
            </p>
          </section>
        )}
      </div>

      <footer className="border-t border-line bg-paper px-5 pb-[max(1rem,env(safe-area-inset-bottom))] pt-4 sm:px-8">
        <div className="grid grid-cols-2 gap-2">
          {saved ? (
            <p
              role="status"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-good-wash text-sm font-medium text-good sm:h-10"
            >
              <Check className="h-4 w-4" aria-hidden />
              Salvata
            </p>
          ) : (
            <Button variant="outline" disabled={isSaving} onClick={() => void save(view)}>
              <Bookmark className="h-4 w-4" aria-hidden />
              Salva
            </Button>
          )}
          <Button disabled={preparing} onClick={() => void prepare()} className="leading-tight">
            {preparing ? "Preparo…" : "Prepara CV e lettera"}
          </Button>
          {view.sourceUrl ? (
            <Button asChild variant="outline">
              <a href={view.sourceUrl} target="_blank" rel="noreferrer">
                Apri l'annuncio
                <ArrowUpRight className="h-4 w-4" aria-hidden />
              </a>
            </Button>
          ) : (
            <span />
          )}
          <StatusMenu value={status} onChange={(v) => void changeStatus(v)} disabled={isSaving} />
        </div>
      </footer>
    </>
  );
}
