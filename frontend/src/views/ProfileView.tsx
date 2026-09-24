import { useCurrentUser } from "@/hooks/useCurrentUser";
import { PersonalInfoCard } from "./profile/PersonalInfoCard";
import { SoftSkillsPanel } from "./profile/SoftSkillsPanel";
import { LanguagesPanel } from "./profile/LanguagesPanel";
import { HardSkillsPanel } from "./profile/HardSkillsPanel";
import { ExperiencesPanel } from "./profile/ExperiencesPanel";
import { EducationPanel } from "./profile/EducationPanel";

export function ProfileView() {
  const { user, userId, isBooting } = useCurrentUser();

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <header>
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-ink-faint">
          Passo uno
        </p>
        <h1 className="font-serif text-5xl leading-none">Chi sei</h1>
        <p className="mt-4 max-w-2xl text-ink-soft">
          Questo profilo vale per tutte le ricerche. Le competenze tecniche specifiche
          di un ruolo le indicherai dopo, quando crei la ricerca.
        </p>
      </header>

      {isBooting ? (
        <div className="rounded border border-line bg-paper-2 p-8 text-ink-faint">
          Caricamento…
        </div>
      ) : (
        <>
          <PersonalInfoCard user={user} />
          {userId && (
            <>
              <SoftSkillsPanel userId={userId} />
              <LanguagesPanel userId={userId} />
              <HardSkillsPanel userId={userId} />
              <ExperiencesPanel userId={userId} />
              <EducationPanel userId={userId} />
            </>
          )}
        </>
      )}
    </div>
  );
}
