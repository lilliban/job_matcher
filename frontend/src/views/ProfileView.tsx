import { Loading, PageHeader } from "@/components/Page";
import { DocumentCheck } from "@/components/illustrations";
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
    return <div className="mx-auto max-w-4xl"><Loading /></div>;
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

/** Titolo + barra di completezza: dice cosa manca invece di
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
    <div className="space-y-4">
      <PageHeader
        title="Profilo"
        art={<DocumentCheck className="w-full" />}
        lead={
          loading
            ? "Guardo a che punto è il tuo profilo…"
            : pct === 100
              ? `Ciao ${first}, il profilo è completo. Aggiornalo quando cambia qualcosa: le ricerche partono da qui.`
              : `Ciao ${first}, il profilo è completo al ${pct}%. Ti manca: ${missing.join(", ")}.`
        }
      />
      <div
        className="h-1.5 w-full max-w-2xl overflow-hidden rounded-full bg-accent-wash"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Completezza del profilo"
      >
        <div className="h-full bg-accent transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
