import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { EyeOff } from "lucide-react";

import { Hint, Loading, PageHeader } from "@/components/Page";
import { useDeleteSession, useSessionsOverview, type SessionOverview } from "@/api/queries";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { cn } from "@/lib/utils";
import { useAppState } from "@/stores/useAppState";
import { SessionWorkspace } from "./sessions/SessionWorkspace";

const STATUS_LABEL: Record<string, string> = {
  draft: "Da avviare",
  running: "In corso",
  completed: "Completata",
  error: "Non riuscita",
  cancelled: "Annullata",
};

const MODE_LABEL: Record<string, string> = {
  companies: "Mie aziende",
  market: "Tutto il mercato",
  both: "Aziende e mercato",
};

/** Ricerche identiche (stesso nome, paese e stato) diventano una riga sola. */
interface SearchGroup {
  key: string;
  latest: SessionOverview;
  ids: string[];
  count: number;
}

function groupSessions(list: SessionOverview[]): SearchGroup[] {
  const map = new Map<string, SearchGroup>();
  for (const s of list) {
    const key = [(s.role_title || "").trim().toLowerCase(), s.preferred_country ?? "", s.status].join("|");
    const g = map.get(key);
    if (!g) {
      map.set(key, { key, latest: s, ids: [s.id], count: 1 });
    } else {
      g.ids.push(s.id);
      g.count += 1;
      if (s.created_at > g.latest.created_at) g.latest = s;
    }
  }
  return [...map.values()].sort((a, b) => b.latest.created_at.localeCompare(a.latest.created_at));
}

/** Nascoste di default: mai avviate, oppure finite senza nemmeno un annuncio. */
function isQuiet(s: SessionOverview): boolean {
  return s.status === "draft" || (s.listings_count === 0 && s.status !== "running");
}

/** Storico: l'elenco delle ricerche già fatte. Le nuove si lanciano da Ricerche. */
export function ReportView() {
  const { userId, isBooting } = useCurrentUser();
  const sessionId = useAppState((s) => s.sessionId);
  const setSessionId = useAppState((s) => s.setSessionId);
  const hiddenIds = useAppState((s) => s.hiddenSessionIds);
  const hideSessions = useAppState((s) => s.hideSessions);
  const unhideSessions = useAppState((s) => s.unhideSessions);
  const overview = useSessionsOverview(userId);
  const deleteSession = useDeleteSession(userId ?? "");

  const [showQuiet, setShowQuiet] = useState(false);
  const [showHidden, setShowHidden] = useState(false);

  const sessions = useMemo(() => overview.data ?? [], [overview.data]);
  const hidden = useMemo(() => new Set(hiddenIds), [hiddenIds]);

  const groups = useMemo(() => groupSessions(sessions), [sessions]);
  const isHidden = (g: SearchGroup) => g.ids.every((id) => hidden.has(id));
  const hiddenGroups = groups.filter(isHidden);
  const quietGroups = groups.filter((g) => !isHidden(g) && isQuiet(g.latest));
  const visibleGroups = groups.filter(
    (g) => (showHidden || !isHidden(g)) && (showQuiet || !isQuiet(g.latest) || isHidden(g)),
  );

  // La ricerca aperta: quella scelta, se è ancora in elenco; altrimenti la prima visibile.
  const openId =
    sessionId && visibleGroups.some((g) => g.ids.includes(sessionId))
      ? sessionId
      : (visibleGroups[0]?.latest.id ?? null);

  useEffect(() => {
    if (openId && openId !== sessionId) setSessionId(openId);
  }, [openId, sessionId, setSessionId]);

  function handleDelete(id: string) {
    const s = sessions.find((x) => x.id === id);
    if (!confirm(`Eliminare la ricerca «${s?.role_title || "qualsiasi ruolo"}»?`)) return;
    deleteSession.mutate(id, {
      onSuccess: () => {
        toast.success("Ricerca eliminata");
        if (sessionId === id) setSessionId(null);
      },
    });
  }

  function handleHide(g: SearchGroup) {
    hideSessions(g.ids);
    toast("Ricerca nascosta dallo Storico", {
      action: { label: "Annulla", onClick: () => unhideSessions(g.ids) },
    });
  }

  const header = (
    <PageHeader
      title="Storico"
      lead={
        <>
          Le ricerche che hai già fatto. Per lanciarne una nuova vai in{" "}
          <Link to="/ricerche" className="font-medium text-ink underline underline-offset-4">
            Ricerche
          </Link>
          .
        </>
      }
    />
  );

  if (isBooting || overview.isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-6">
        {header}
        <Loading />
      </div>
    );
  }

  if (!userId || sessions.length === 0) {
    return (
      <div className="mx-auto max-w-6xl space-y-6">
        {header}
        <Hint>
          {!userId
            ? "Crea prima il tuo profilo: poi qui trovi tutte le tue ricerche."
            : "Non hai ancora fatto nessuna ricerca. Quando ne avvii una, la trovi qui."}
        </Hint>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {header}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside aria-label="Le tue ricerche" className="space-y-3 lg:sticky lg:top-8 lg:self-start">
          <div className="flex flex-wrap gap-2">
            {quietGroups.length > 0 && (
              <ToggleChip active={showQuiet} onClick={() => setShowQuiet((v) => !v)}>
                Senza annunci o da avviare
                <span className="font-mono text-xs opacity-80">{quietGroups.length}</span>
              </ToggleChip>
            )}
            {hiddenGroups.length > 0 && (
              <ToggleChip active={showHidden} onClick={() => setShowHidden((v) => !v)}>
                Nascoste
                <span className="font-mono text-xs opacity-80">{hiddenGroups.length}</span>
              </ToggleChip>
            )}
          </div>

          {visibleGroups.length === 0 ? (
            <p className="rounded-xl bg-surface px-4 py-3 text-sm text-ink-soft">
              Nessuna ricerca da mostrare con questi filtri.
            </p>
          ) : (
            <ul className="space-y-2">
              {visibleGroups.map((g) => (
                <li key={g.key}>
                  <SearchRow
                    g={g}
                    active={!!openId && g.ids.includes(openId)}
                    hidden={isHidden(g)}
                    onOpen={() => setSessionId(g.latest.id)}
                    onHide={() => handleHide(g)}
                    onUnhide={() => unhideSessions(g.ids)}
                  />
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section aria-label="Dettaglio ricerca" className="min-w-0">
          {openId && (
            <SessionWorkspace
              key={openId}
              userId={userId}
              sessionId={openId}
              onDelete={() => handleDelete(openId)}
            />
          )}
        </section>
      </div>
    </div>
  );
}

function ToggleChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "jm-press inline-flex h-10 items-center gap-2 rounded-full border px-4 text-sm font-medium",
        active ? "border-accent bg-accent text-paper-2" : "border-line-hard bg-paper-2 text-ink hover:border-accent",
      )}
    >
      {children}
    </button>
  );
}

function SearchRow({
  g,
  active,
  hidden,
  onOpen,
  onHide,
  onUnhide,
}: {
  g: SearchGroup;
  active: boolean;
  hidden: boolean;
  onOpen: () => void;
  onHide: () => void;
  onUnhide: () => void;
}) {
  const s = g.latest;
  const isError = s.status === "error";
  return (
    <div
      className={cn(
        "relative flex items-start gap-2 rounded-2xl border bg-paper-2 p-1 transition-colors",
        active ? "border-accent" : "border-line hover:border-line-hard",
        hidden && "opacity-70",
      )}
    >
      <button
        type="button"
        onClick={onOpen}
        aria-current={active ? "true" : undefined}
        className="min-w-0 flex-1 rounded-xl p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
      >
        <span className="flex items-baseline gap-2">
          <span className="truncate text-[15px] font-medium">{s.role_title || "Qualsiasi ruolo adatto a te"}</span>
          {g.count > 1 && (
            <span
              className="shrink-0 rounded-full bg-surface px-2 py-0.5 font-mono text-xs text-ink-soft"
              title={`${g.count} ricerche uguali: mostro la più recente`}
            >
              ×{g.count}
            </span>
          )}
        </span>
        <span className="mt-1 block truncate text-xs text-ink-faint">
          {MODE_LABEL[s.search_mode] ?? s.search_mode}
          {s.preferred_country && ` · ${s.preferred_country}`}
          {` · ${new Date(s.created_at).toLocaleDateString("it-IT")}`}
        </span>
        <span className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          <span className={cn(isError ? "text-bad" : "text-ink-soft")}>
            {STATUS_LABEL[s.status] ?? s.status}
          </span>
          <span className="text-ink-faint">·</span>
          <span className="text-ink-soft">
            <strong className="font-semibold text-ink">{s.matches_count}</strong> match su {s.listings_count} annunci
          </span>
          {s.new_matches > 0 && (
            <span className="rounded-full bg-good-wash px-2 py-0.5 font-medium text-good">
              {s.new_matches} da vedere
            </span>
          )}
        </span>
      </button>
      {hidden ? (
        <button
          type="button"
          onClick={onUnhide}
          className="jm-press m-1 inline-flex h-10 shrink-0 items-center rounded-full px-3 text-sm text-ink-soft hover:bg-surface hover:text-ink"
        >
          Mostra
        </button>
      ) : (
        <button
          type="button"
          onClick={onHide}
          aria-label={`Nascondi la ricerca ${s.role_title || "qualsiasi ruolo"}`}
          title="Nascondi dallo Storico"
          className="jm-press m-1 grid h-10 w-10 shrink-0 place-items-center rounded-full text-ink-faint hover:bg-surface hover:text-ink"
        >
          <EyeOff className="h-4 w-4" aria-hidden />
        </button>
      )}
    </div>
  );
}
