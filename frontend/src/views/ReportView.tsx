import { useEffect } from "react";
import { toast } from "sonner";
import { Building2, Globe2, Layers, Trash2 } from "lucide-react";

import { Guide } from "@/components/Avatar";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useDeleteSession, useSessionsOverview, type SessionOverview } from "@/api/queries";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useAppState } from "@/stores/useAppState";
import { SessionWorkspace } from "./sessions/SessionWorkspace";

const STATUS: Record<string, { label: string; variant: "default" | "good" | "warn" | "bad" | "outline" }> = {
  draft: { label: "Da avviare", variant: "outline" },
  running: { label: "In corso", variant: "warn" },
  completed: { label: "Completata", variant: "good" },
  error: { label: "Errore", variant: "bad" },
  cancelled: { label: "Annullata", variant: "outline" },
};

const MODE_ICON: Record<string, React.ReactNode> = {
  companies: <Building2 className="h-3.5 w-3.5" />,
  market: <Globe2 className="h-3.5 w-3.5" />,
  both: <Layers className="h-3.5 w-3.5" />,
};
const MODE_LABEL: Record<string, string> = {
  companies: "Mie aziende",
  market: "Tutto il mercato",
  both: "Aziende + mercato",
};

export function ReportView() {
  const { userId, isBooting } = useCurrentUser();
  const sessionId = useAppState((s) => s.sessionId);
  const setSessionId = useAppState((s) => s.setSessionId);
  const overview = useSessionsOverview(userId);
  const deleteSession = useDeleteSession(userId ?? "");

  const sessions = overview.data ?? [];

  // Nessuna selezione valida → apre la più recente.
  useEffect(() => {
    if (sessions.length === 0) return;
    if (!sessionId || !sessions.some((s) => s.id === sessionId)) {
      setSessionId(sessions[0].id);
    }
  }, [sessions, sessionId, setSessionId]);

  if (isBooting || overview.isLoading) return <div className="text-ink-faint">Caricamento…</div>;

  if (!userId) {
    return (
      <div className="mx-auto max-w-3xl">
        <Guide>Crea prima il tuo profilo: poi qui trovi tutte le tue ricerche.</Guide>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <Guide>Non hai ancora fatto nessuna ricerca. Quando ne avvii una, la trovi qui.</Guide>
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside aria-label="Le tue ricerche" className="space-y-3 lg:sticky lg:top-8 lg:self-start">
        <h1 className="font-serif text-3xl">Le tue ricerche</h1>
        <ul className="space-y-2">
          {sessions.map((s) => (
            <li key={s.id}>
              <SearchRow
                s={s}
                active={s.id === sessionId}
                onOpen={() => setSessionId(s.id)}
                onDelete={() => {
                  if (!confirm(`Eliminare la ricerca «${s.role_title || "qualsiasi ruolo"}»?`)) return;
                  deleteSession.mutate(s.id, {
                    onSuccess: () => {
                      toast.success("Ricerca eliminata");
                      if (sessionId === s.id) setSessionId(null);
                    },
                  });
                }}
              />
            </li>
          ))}
        </ul>
      </aside>

      <section aria-label="Dettaglio ricerca" className="min-w-0">
        {sessionId && sessions.some((s) => s.id === sessionId) && (
          <SessionWorkspace key={sessionId} userId={userId} sessionId={sessionId} />
        )}
      </section>
    </div>
  );
}

function SearchRow({
  s, active, onOpen, onDelete,
}: { s: SessionOverview; active: boolean; onOpen: () => void; onDelete: () => void }) {
  const st = STATUS[s.status] ?? { label: s.status, variant: "outline" as const };
  return (
    <Card
      className={
        "group relative transition-colors " +
        (active ? "border-accent ring-2 ring-accent/20" : "hover:border-line-hard")
      }
    >
      <button
        type="button"
        onClick={onOpen}
        aria-current={active}
        className="block w-full p-4 pr-10 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
      >
        <span className="block truncate font-serif text-lg">
          {s.role_title || "Qualsiasi ruolo adatto a te"}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-faint">
          <span className="flex items-center gap-1">
            {MODE_ICON[s.search_mode] ?? null}
            {MODE_LABEL[s.search_mode] ?? s.search_mode}
          </span>
          {s.preferred_country && <span>· {s.preferred_country}</span>}
          <span>· {new Date(s.created_at).toLocaleDateString("it-IT")}</span>
        </span>
        <span className="mt-3 flex flex-wrap items-center gap-2">
          <Badge variant={st.variant}>{st.label}</Badge>
          <span className="text-xs text-ink-soft">
            <strong className="font-semibold text-ink">{s.matches_count}</strong> match su {s.listings_count} annunci
          </span>
          {s.new_matches > 0 && <Badge variant="good">{s.new_matches} da vedere</Badge>}
        </span>
        {s.best_score != null && (
          <span className="mt-2 block text-xs text-ink-faint">
            Migliore: {Math.round(s.best_score * 100)}%
          </span>
        )}
      </button>
      <button
        type="button"
        onClick={onDelete}
        aria-label="Elimina ricerca"
        className="absolute right-2 top-2 rounded-sm p-1.5 text-ink-faint opacity-0 hover:bg-bad-wash hover:text-bad focus-visible:opacity-100 group-hover:opacity-100"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </Card>
  );
}
