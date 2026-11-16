import { useCallback } from "react";
import { toast } from "sonner";

import { useSaveFeedMatch, useUpdateMatchStatus } from "@/api/queries";
import { useCurrentUser } from "@/hooks/useCurrentUser";

import { REMOVE_VALUE, STATUS_LABEL, isTracked, type MatchView } from "./matchModel";

function message(err: unknown): string {
  return err instanceof Error ? err.message : "Qualcosa non ha funzionato. Riprova.";
}

/**
 * Le azioni sulle candidature, uguali ovunque (dettaglio del feed, di una ricerca,
 * righe di Candidature): salvare, cambiare stato, toglierla.
 */
export function useMatchActions() {
  const { userId } = useCurrentUser();
  const saveFeed = useSaveFeedMatch(userId);
  const updateStatus = useUpdateMatchStatus();

  const patch = useCallback(
    (matchId: string, status: string) => updateStatus.mutateAsync({ matchId, body: { status } }),
    [updateStatus],
  );

  /** Porta l'annuncio tra le candidature (se non c'è già) e ne ritorna l'id; null se non riesce. */
  const ensureSaved = useCallback(
    async (view: MatchView): Promise<string | null> => {
      try {
        if (view.matchId && isTracked(view.status)) return view.matchId;
        if (view.matchId) {
          await patch(view.matchId, "saved");
          return view.matchId;
        }
        if (!view.feed) return null;
        const saved = await saveFeed.mutateAsync({ ad: view.feed });
        return saved.id;
      } catch (err) {
        toast.error(message(err));
        return null;
      }
    },
    [patch, saveFeed],
  );

  /** "Salva": lo stesso di ensureSaved, con la conferma a video. */
  const save = useCallback(
    async (view: MatchView) => {
      const id = await ensureSaved(view);
      if (id) toast.success("Salvata tra le candidature");
      return id;
    },
    [ensureSaved],
  );

  /** Cambia lo stato. Su un annuncio del feed non ancora salvato lo salva con quello stato. */
  const setStatus = useCallback(
    async (view: MatchView, next: string): Promise<boolean> => {
      const previous = view.status;
      try {
        if (next === REMOVE_VALUE) {
          if (!view.matchId) return false;
          await patch(view.matchId, "new");
          toast("Tolta dalle candidature", {
            action: {
              label: "Annulla",
              onClick: () => {
                if (view.matchId && isTracked(previous)) void patch(view.matchId, previous);
              },
            },
          });
          return true;
        }
        if (view.matchId) {
          await patch(view.matchId, next);
        } else if (view.feed) {
          await saveFeed.mutateAsync({ ad: view.feed, status: next });
        } else {
          return false;
        }
        toast.success(`Segnata come «${STATUS_LABEL[next] ?? next}»`);
        return true;
      } catch (err) {
        toast.error(message(err));
        return false;
      }
    },
    [patch, saveFeed],
  );

  return { ensureSaved, save, setStatus, isSaving: saveFeed.isPending || updateStatus.isPending };
}
