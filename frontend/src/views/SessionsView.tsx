import { Card } from "@/components/ui/card";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useAppState } from "@/stores/useAppState";
import { NewSessionForm } from "./sessions/NewSessionForm";
import { SessionsList } from "./sessions/SessionsList";
import { SessionWorkspace } from "./sessions/SessionWorkspace";

export function SessionsView() {
  const { userId, isBooting } = useCurrentUser();
  const sessionId = useAppState((s) => s.sessionId);

  if (isBooting) return <div className="text-ink-faint">Caricamento…</div>;

  if (!userId) {
    return (
      <div className="mx-auto max-w-3xl">
        <Header />
        <Card className="p-8 text-ink-soft">
          Crea prima il tuo profilo (Passo uno) per iniziare le ricerche.
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <Header />
      <NewSessionForm userId={userId} />
      <section>
        <h2 className="mb-4 font-serif text-2xl">Le tue ricerche</h2>
        <SessionsList userId={userId} />
      </section>
      {sessionId && <SessionWorkspace userId={userId} sessionId={sessionId} />}
    </div>
  );
}

function Header() {
  return (
    <header className="mb-8">
      <p className="mb-2 font-mono text-xs uppercase tracking-widest text-ink-faint">
        Passo tre
      </p>
      <h1 className="font-serif text-5xl leading-none">Cosa cerchi</h1>
      <p className="mt-4 max-w-2xl text-ink-soft">
        Una ricerca per ogni mestiere. Puoi cercare come data analyst e come barista in
        parallelo: sono due ricerche separate, stesso profilo.
      </p>
    </header>
  );
}
