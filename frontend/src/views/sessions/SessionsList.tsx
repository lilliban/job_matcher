import { toast } from "sonner";
import { Play, Trash2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useDeleteSession, useSessions } from "@/api/queries";
import { useAppState } from "@/stores/useAppState";

const STATUS_VARIANT: Record<string, "default" | "good" | "warn" | "bad" | "outline"> = {
  draft: "outline",
  running: "warn",
  completed: "good",
  error: "bad",
  cancelled: "outline",
};

export function SessionsList({ userId }: { userId: string }) {
  const sessionsQuery = useSessions(userId);
  const deleteSession = useDeleteSession(userId);
  const sessionId = useAppState((s) => s.sessionId);
  const setSessionId = useAppState((s) => s.setSessionId);

  if (sessionsQuery.isLoading) return <div className="text-ink-faint">Carico le ricerche…</div>;
  if ((sessionsQuery.data ?? []).length === 0) {
    return (
      <div className="rounded border border-dashed border-line bg-paper-2 p-6 text-sm text-ink-faint">
        Nessuna ricerca ancora. Creane una qui sopra.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {sessionsQuery.data!.map((s) => (
        <Card
          key={s.id}
          className={
            "cursor-pointer p-4 transition-colors " +
            (sessionId === s.id ? "border-accent ring-2 ring-accent/20" : "hover:border-line-hard")
          }
          onClick={() => setSessionId(s.id)}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Play className="h-3 w-3 text-ink-faint" />
                <span className="truncate font-serif text-lg">{s.role_title}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
                <span>{new Date(s.created_at).toLocaleDateString("it-IT")}</span>
                {s.preferred_country && <span>· {s.preferred_country}</span>}
                <Badge variant={STATUS_VARIANT[s.status] ?? "outline"}>{s.status}</Badge>
              </div>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (confirm(`Eliminare la ricerca "${s.role_title}"?`)) {
                  deleteSession.mutate(s.id, {
                    onSuccess: () => {
                      toast.success("Ricerca eliminata");
                      if (sessionId === s.id) setSessionId(null);
                    },
                  });
                }
              }}
              className="rounded-sm p-1 text-ink-faint hover:bg-line/50 hover:text-bad"
              aria-label="Elimina ricerca"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </Card>
      ))}
    </div>
  );
}
