import { type ReactNode, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  useAddEducation,
  useAddExperience,
  useAddHardSkill,
  useAddLanguage,
  useAddSoftSkill,
  useUpdateUser,
} from "@/api/queries";
import type { CVParseResult } from "@/api/schemas";

interface Props {
  userId: string;
  result: CVParseResult;
  onClose: () => void;
}

type ListKey = "hardSkills" | "softSkills" | "languages" | "experiences" | "education";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-faint">{title}</p>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function CheckRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="flex items-start gap-2 rounded-sm border border-line bg-paper-2 px-3 py-2 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
      />
      <span>{label}</span>
    </label>
  );
}

export function CVReviewSheet({ userId, result, onClose }: Props) {
  const { profile, critique } = result;
  const languages = profile.languages as Array<{ language?: string; level?: string }>;

  const [bioChecked, setBioChecked] = useState(!!profile.bio);
  const [phoneChecked, setPhoneChecked] = useState(!!profile.phone);
  const [locationChecked, setLocationChecked] = useState(!!profile.location);
  const [selected, setSelected] = useState<Record<ListKey, Set<number>>>({
    hardSkills: new Set(profile.hard_skills.map((_, i) => i)),
    softSkills: new Set(profile.soft_skills.map((_, i) => i)),
    languages: new Set(languages.map((_, i) => i)),
    experiences: new Set(profile.experiences.map((_, i) => i)),
    education: new Set(profile.education.map((_, i) => i)),
  });
  const [applying, setApplying] = useState(false);

  const updateUser = useUpdateUser(userId);
  const addHardSkill = useAddHardSkill(userId);
  const addSoftSkill = useAddSoftSkill(userId);
  const addLanguage = useAddLanguage(userId);
  const addExperience = useAddExperience(userId);
  const addEducation = useAddEducation(userId);

  function toggle(key: ListKey, idx: number) {
    setSelected((s) => {
      const next = new Set(s[key]);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return { ...s, [key]: next };
    });
  }

  async function handleApply() {
    setApplying(true);
    const tasks: Promise<unknown>[] = [];

    const patch: Record<string, string> = {};
    if (bioChecked && profile.bio) patch.bio = profile.bio;
    if (phoneChecked && profile.phone) patch.phone = profile.phone;
    if (locationChecked && profile.location) patch.location = profile.location;
    if (Object.keys(patch).length > 0) tasks.push(updateUser.mutateAsync(patch));

    profile.hard_skills.forEach((name, i) => {
      if (selected.hardSkills.has(i))
        tasks.push(addHardSkill.mutateAsync({ name, level: "intermediate", years_exp: 0 }));
    });
    profile.soft_skills.forEach((name, i) => {
      if (selected.softSkills.has(i)) tasks.push(addSoftSkill.mutateAsync({ name }));
    });
    languages.forEach((lang, i) => {
      if (selected.languages.has(i) && lang.language) {
        const level = lang.level ?? "B1";
        tasks.push(
          addLanguage.mutateAsync({
            language: lang.language,
            level,
            is_native: /madrelingua|native/i.test(level),
          }),
        );
      }
    });
    profile.experiences.forEach((exp, i) => {
      if (selected.experiences.has(i) && exp.company && exp.role) {
        tasks.push(
          addExperience.mutateAsync({
            company: exp.company,
            role: exp.role,
            start_date: exp.start_date ?? null,
            end_date: exp.end_date ?? null,
            description: exp.description ?? null,
          }),
        );
      }
    });
    profile.education.forEach((edu, i) => {
      if (selected.education.has(i) && edu.institution) {
        tasks.push(
          addEducation.mutateAsync({
            institution: edu.institution,
            degree: edu.degree ?? null,
            field: edu.field ?? null,
            year: edu.year ?? null,
          }),
        );
      }
    });

    const results = await Promise.allSettled(tasks);
    const ok = results.filter((r) => r.status === "fulfilled").length;
    const fail = results.length - ok;

    setApplying(false);
    if (fail === 0) toast.success(`Importato dal CV: ${ok} elementi`);
    else toast.error(`${ok} importati, ${fail} falliti`);
    onClose();
  }

  const hasNothingToShow =
    !profile.bio &&
    !profile.phone &&
    !profile.location &&
    profile.hard_skills.length === 0 &&
    profile.soft_skills.length === 0 &&
    languages.length === 0 &&
    profile.experiences.length === 0 &&
    profile.education.length === 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-4 sm:items-center"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded border border-line bg-paper shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line p-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-ink-faint">CV importato</p>
            <h3 className="font-serif text-xl">Cosa vuoi aggiungere al profilo?</h3>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Chiudi
          </Button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto p-6 text-sm">
          {hasNothingToShow && (
            <p className="text-ink-faint">
              Non sono riuscito a estrarre dati strutturati da questo CV.
            </p>
          )}

          {(profile.bio || profile.phone || profile.location) && (
            <Section title="Anagrafica">
              {profile.bio && (
                <CheckRow
                  label={`Bio: "${profile.bio}"`}
                  checked={bioChecked}
                  onChange={() => setBioChecked((v) => !v)}
                />
              )}
              {profile.phone && (
                <CheckRow
                  label={`Telefono: ${profile.phone}`}
                  checked={phoneChecked}
                  onChange={() => setPhoneChecked((v) => !v)}
                />
              )}
              {profile.location && (
                <CheckRow
                  label={`Località: ${profile.location}`}
                  checked={locationChecked}
                  onChange={() => setLocationChecked((v) => !v)}
                />
              )}
            </Section>
          )}

          {profile.hard_skills.length > 0 && (
            <Section title={`Competenze tecniche (${profile.hard_skills.length})`}>
              {profile.hard_skills.map((name, i) => (
                <CheckRow
                  key={i}
                  label={name}
                  checked={selected.hardSkills.has(i)}
                  onChange={() => toggle("hardSkills", i)}
                />
              ))}
            </Section>
          )}

          {profile.soft_skills.length > 0 && (
            <Section title={`Soft skill (${profile.soft_skills.length})`}>
              {profile.soft_skills.map((name, i) => (
                <CheckRow
                  key={i}
                  label={name}
                  checked={selected.softSkills.has(i)}
                  onChange={() => toggle("softSkills", i)}
                />
              ))}
            </Section>
          )}

          {languages.length > 0 && (
            <Section title={`Lingue (${languages.length})`}>
              {languages.map((lang, i) => (
                <CheckRow
                  key={i}
                  label={`${lang.language ?? "?"} — ${lang.level ?? "?"}`}
                  checked={selected.languages.has(i)}
                  onChange={() => toggle("languages", i)}
                />
              ))}
            </Section>
          )}

          {profile.experiences.length > 0 && (
            <Section title={`Esperienze (${profile.experiences.length})`}>
              {profile.experiences.map((exp, i) => (
                <CheckRow
                  key={i}
                  label={`${exp.role ?? "?"} presso ${exp.company ?? "?"} (${exp.start_date ?? "?"} – ${exp.end_date ?? "oggi"})`}
                  checked={selected.experiences.has(i)}
                  onChange={() => toggle("experiences", i)}
                />
              ))}
            </Section>
          )}

          {profile.education.length > 0 && (
            <Section title={`Formazione (${profile.education.length})`}>
              {profile.education.map((edu, i) => (
                <CheckRow
                  key={i}
                  label={`${edu.degree ?? "?"} in ${edu.field ?? "?"} — ${edu.institution ?? "?"} (${edu.year ?? "?"})`}
                  checked={selected.education.has(i)}
                  onChange={() => toggle("education", i)}
                />
              ))}
            </Section>
          )}

          {critique && (
            <Section title="Feedback sul CV">
              <p className="whitespace-pre-wrap rounded-sm border border-line bg-paper-2 px-3 py-2 text-ink-faint">
                {critique}
              </p>
            </Section>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-line bg-paper-2 p-3">
          <Button variant="ghost" onClick={onClose} disabled={applying}>
            Annulla
          </Button>
          <Button onClick={handleApply} disabled={applying || hasNothingToShow}>
            {applying ? "Applico…" : "Applica selezionati"}
          </Button>
        </footer>
      </div>
    </div>
  );
}
