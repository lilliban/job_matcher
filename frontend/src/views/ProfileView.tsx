import { Guide } from "@/components/Avatar";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import {
  useEducation,
  useExperiences,
  useHardSkills,
  useLanguages,
  useSoftSkills,
} from "@/api/queries";
import { Onboarding } from "./profile/Onboarding";
import { PersonalInfoCard } from "./profile/PersonalInfoCard";
import { SoftSkillsPanel } from "./profile/SoftSkillsPanel";
import { LanguagesPanel } from "./profile/LanguagesPanel";
import { HardSkillsPanel } from "./profile/HardSkillsPanel";
import { ExperiencesPanel } from "./profile/ExperiencesPanel";
import { EducationPanel } from "./profile/EducationPanel";

export function ProfileView() {
  const { user, userId, isBooting } = useCurrentUser();

  if (isBooting) {
    return <div className="mx-auto max-w-4xl text-ink-faint">Caricamento…</div>;
  }

  if (!user || !userId) {
    return (
      <div className="mx-auto max-w-4xl">
        <Onboarding />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <ProfileHeader userId={userId} name={user.name} />
      <PersonalInfoCard user={user} />
      <HardSkillsPanel userId={userId} />
      <SoftSkillsPanel userId={userId} />
      <LanguagesPanel userId={userId} />
      <ExperiencesPanel userId={userId} />
      <EducationPanel userId={userId} />
    </div>
  );
}

/** Saluto dell'assistente + barra di completezza: dice cosa manca invece di
 *  lasciare l'utente a indovinare se il profilo è "abbastanza". */
function ProfileHeader({ userId, name }: { userId: string; name: string }) {
  const hard = useHardSkills(userId);
  const soft = useSoftSkills(userId);
  const langs = useLanguages(userId);
  const exps = useExperiences(userId);
  const edu = useEducation(userId);

  const checks: Array<[string, boolean]> = [
    ["competenze tecniche", (hard.data?.length ?? 0) >= 3],
    ["soft skill", (soft.data?.length ?? 0) >= 1],
    ["lingue", (langs.data?.length ?? 0) >= 1],
    ["esperienze", (exps.data?.length ?? 0) >= 1],
    ["formazione", (edu.data?.length ?? 0) >= 1],
  ];
  const done = checks.filter(([, ok]) => ok).length;
  const pct = Math.round((done / checks.length) * 100);
  const missing = checks.filter(([, ok]) => !ok).map(([label]) => label);
  const loading = [hard, soft, langs, exps, edu].some((q) => q.isLoading);
  const first = name.trim().split(/\s+/)[0];

  return (
    <header className="space-y-4">
      <Guide waving={pct < 100} size={84}>
        <p className="font-serif text-2xl">Ciao {first}!</p>
        <p className="mt-1 text-ink-soft">
          {loading
            ? "Guardo a che punto è il tuo profilo…"
            : pct === 100
              ? "Il profilo è completo. Più è preciso, meglio lavorano le ricerche: aggiornalo quando cambia qualcosa."
              : `Il profilo è completo al ${pct}%. Ti manca: ${missing.join(", ")}.`}
        </p>
      </Guide>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-line"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Completezza del profilo"
      >
        <div className="h-full bg-accent transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
    </header>
  );
}
