import { useRef, useState } from "react";
import { toast } from "sonner";
import { FileUp, Loader2, PencilLine, Plus, Trash2, X } from "lucide-react";

import { Hint, PageHeader } from "@/components/Page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateProfile, useParseCv, type CvDraft, type ParsedCv } from "@/api/queries";
import { dedupeSoftSkills } from "@/lib/softSkills";
import { useAppState } from "@/stores/useAppState";

type Step = "choose" | "upload" | "review" | "manual";

const LANGUAGES: Array<[string, string]> = [
  ["italian", "Italiano"],
  ["english", "Inglese"],
  ["german", "Tedesco"],
  ["french", "Francese"],
  ["spanish", "Spagnolo"],
  ["portuguese", "Portoghese"],
  ["dutch", "Olandese"],
];
const LEVELS = ["madrelingua", "A1", "A2", "B1", "B2", "C1", "C2"];

const selectClass =
  "h-11 rounded-xl border border-field bg-paper-2 px-3 text-sm sm:h-10";

const emptyDraft: CvDraft = {
  name: "",
  email: "",
  phone: "",
  location: "",
  bio: "",
  hard_skills: [],
  soft_skills: [],
  languages: [],
  experiences: [],
  education: [],
};

function draftFromParsed(p: ParsedCv["profile"]): CvDraft {
  const s = (v: unknown) => (typeof v === "string" ? v : "");
  return {
    name: s(p.name),
    email: s(p.email),
    phone: s(p.phone),
    location: s(p.location),
    bio: s(p.bio),
    hard_skills: p.hard_skills ?? [],
    soft_skills: dedupeSoftSkills(p.soft_skills ?? []),
    languages: (p.languages ?? [])
      .filter((l) => l.language)
      .map((l) => ({
        language: String(l.language).toLowerCase(),
        level: l.level ? String(l.level) : "B1",
      })),
    experiences: (p.experiences ?? []).map((e) => ({
      company: s(e.company),
      role: s(e.role),
      start_date: s(e.start_date),
      end_date: s(e.end_date),
      description: s(e.description),
    })),
    education: (p.education ?? []).map((e) => ({
      institution: s(e.institution),
      degree: s(e.degree),
      field: s(e.field),
      year: s(e.year),
    })),
  };
}

export function Onboarding() {
  const [step, setStep] = useState<Step>("choose");
  const [draft, setDraft] = useState<CvDraft>(emptyDraft);
  const [cvText, setCvText] = useState<string | null>(null);
  const [critique, setCritique] = useState<string | null>(null);

  const parseCv = useParseCv();
  const createProfile = useCreateProfile();
  const setUserId = useAppState((s) => s.setUserId);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    try {
      const parsed = await parseCv.mutateAsync(file);
      setDraft(draftFromParsed(parsed.profile));
      setCvText(parsed.cv_text);
      setCritique(parsed.critique);
      setStep("review");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossibile leggere il CV");
    }
  }

  async function handleCreate() {
    try {
      const created = await createProfile.mutateAsync({
        ...draft,
        // le righe lasciate vuote durante la revisione non vanno inviate
        hard_skills: draft.hard_skills.filter(Boolean),
        soft_skills: dedupeSoftSkills(draft.soft_skills),
        experiences: draft.experiences.filter((e) => e.company.trim() && e.role.trim()),
        education: draft.education.filter((e) => e.institution.trim()),
        cv_text: cvText,
      });
      setUserId(created.id);
      toast.success("Profilo creato");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore nella creazione del profilo");
    }
  }

  const canCreate = draft.name.trim() !== "" && /\S+@\S+\.\S+/.test(draft.email);

  if (step === "choose") {
    return (
      <div className="space-y-10">
        <PageHeader
          title="Crea il tuo profilo"
          lead="Ci vuole un minuto. Dal profilo partono ruoli, competenze e aziende suggerite."
        />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <ChoiceCard
            icon={<FileUp className="h-6 w-6" />}
            title="Parti dal tuo CV"
            text="Carica il PDF: leggo io i dati e li compilo per te. Prima di salvare puoi correggere tutto."
            tag="Più veloce"
            onClick={() => setStep("upload")}
          />
          <ChoiceCard
            icon={<PencilLine className="h-6 w-6" />}
            title="Compila a mano"
            text="Inserisci i dati un passo alla volta. Con questa scelta non potrai caricare un CV dopo."
            onClick={() => setStep("manual")}
          />
        </div>
      </div>
    );
  }

  if (step === "upload") {
    return (
      <div className="space-y-6">
        <BackLink onClick={() => setStep("choose")} />
        <Hint>Carica il tuo CV in PDF: leggo i dati e te li faccio controllare.</Hint>
        <UploadBox onFile={handleFile} loading={parseCv.isPending} />
      </div>
    );
  }

  if (step === "manual") {
    return (
      <div className="space-y-6">
        <BackLink onClick={() => setStep("choose")} />
        <Hint>Partiamo dalle basi. Il resto lo aggiungi dopo, sezione per sezione.</Hint>
        <Card className="space-y-5 p-5 sm:p-8">
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <Field label="Nome e cognome" value={draft.name} onChange={(v) => setDraft({ ...draft, name: v })} placeholder="Mario Rossi" />
            <Field label="Email" type="email" value={draft.email} onChange={(v) => setDraft({ ...draft, email: v })} placeholder="mario@esempio.it" />
            <Field label="Telefono (facoltativo)" value={draft.phone} onChange={(v) => setDraft({ ...draft, phone: v })} />
            <Field label="Dove vivi" value={draft.location} onChange={(v) => setDraft({ ...draft, location: v })} placeholder="Civitanova Marche, MC" />
          </div>
          <div className="flex justify-end border-t border-line pt-5">
            <Button onClick={handleCreate} disabled={!canCreate || createProfile.isPending}>
              Crea profilo
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  // review
  return (
    <div className="space-y-6">
      <BackLink onClick={() => setStep("upload")} label="Carica un altro CV" />
      <Hint>
        Ecco cosa ho letto. <strong>Controlla e correggi</strong>: a volte sbaglio, soprattutto
        con le date e i layout insoliti. Quando è giusto, crea il profilo.
      </Hint>

      <Card className="space-y-5 p-5 sm:p-8">
        <h2 className="jm-h2">Anagrafica</h2>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <Field label="Nome e cognome" value={draft.name} onChange={(v) => setDraft({ ...draft, name: v })} />
          <Field label="Email" type="email" value={draft.email} onChange={(v) => setDraft({ ...draft, email: v })} warn={!draft.email} hint={!draft.email ? "Non l'ho trovata nel CV: inseriscila" : undefined} />
          <Field label="Telefono" value={draft.phone} onChange={(v) => setDraft({ ...draft, phone: v })} />
          <Field label="Dove vivi" value={draft.location} onChange={(v) => setDraft({ ...draft, location: v })} />
          <div className="space-y-1.5 md:col-span-2">
            <Label>Sintesi professionale</Label>
            <Textarea rows={3} value={draft.bio} onChange={(e) => setDraft({ ...draft, bio: e.target.value })} />
          </div>
        </div>
      </Card>

      <Card className="space-y-5 p-5 sm:p-8">
        <h2 className="jm-h2">Competenze</h2>
        <ChipEditor
          label="Tecniche"
          items={draft.hard_skills}
          onChange={(hard_skills) => setDraft({ ...draft, hard_skills })}
          placeholder="Aggiungi una competenza e premi Invio"
        />
        <ChipEditor
          label="Trasversali"
          items={draft.soft_skills}
          onChange={(soft_skills) => setDraft({ ...draft, soft_skills: dedupeSoftSkills(soft_skills) })}
          placeholder="Es. Lavoro in team"
        />
      </Card>

      <Card className="space-y-4 p-8">
        <h2 className="jm-h2">Lingue</h2>
        {draft.languages.map((l, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <select
              className={selectClass}
              value={l.language}
              onChange={(e) => setDraft({ ...draft, languages: draft.languages.map((x, j) => (j === i ? { ...x, language: e.target.value } : x)) })}
            >
              {!LANGUAGES.some(([v]) => v === l.language) && <option value={l.language}>{l.language}</option>}
              {LANGUAGES.map(([v, label]) => (
                <option key={v} value={v}>{label}</option>
              ))}
            </select>
            <select
              className={selectClass}
              value={LEVELS.includes(l.level) ? l.level : "B1"}
              onChange={(e) => setDraft({ ...draft, languages: draft.languages.map((x, j) => (j === i ? { ...x, level: e.target.value } : x)) })}
            >
              {LEVELS.map((lv) => (
                <option key={lv} value={lv}>{lv}</option>
              ))}
            </select>
            <RemoveButton onClick={() => setDraft({ ...draft, languages: draft.languages.filter((_, j) => j !== i) })} />
          </div>
        ))}
        <AddRow label="Aggiungi lingua" onClick={() => setDraft({ ...draft, languages: [...draft.languages, { language: "english", level: "B2" }] })} />
      </Card>

      <Card className="space-y-4 p-8">
        <h2 className="jm-h2">Esperienze</h2>
        {draft.experiences.map((e, i) => {
          const set = (patch: Partial<typeof e>) =>
            setDraft({ ...draft, experiences: draft.experiences.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
          return (
            <div key={i} className="space-y-3 rounded-xl border border-line bg-paper p-4">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <Field label="Ruolo" value={e.role} onChange={(v) => set({ role: v })} />
                <Field label="Azienda" value={e.company} onChange={(v) => set({ company: v })} />
                <Field label="Dal" value={e.start_date} onChange={(v) => set({ start_date: v })} />
                <Field label="Al (vuoto = in corso)" value={e.end_date} onChange={(v) => set({ end_date: v })} />
              </div>
              <Textarea rows={3} value={e.description} onChange={(ev) => set({ description: ev.target.value })} placeholder="Cosa facevi" />
              <div className="flex justify-end">
                <RemoveButton label="Rimuovi esperienza" onClick={() => setDraft({ ...draft, experiences: draft.experiences.filter((_, j) => j !== i) })} />
              </div>
            </div>
          );
        })}
        <AddRow label="Aggiungi esperienza" onClick={() => setDraft({ ...draft, experiences: [...draft.experiences, { company: "", role: "", start_date: "", end_date: "", description: "" }] })} />
      </Card>

      <Card className="space-y-4 p-8">
        <h2 className="jm-h2">Formazione</h2>
        {draft.education.map((e, i) => {
          const set = (patch: Partial<typeof e>) =>
            setDraft({ ...draft, education: draft.education.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
          return (
            <div key={i} className="grid grid-cols-1 items-end gap-3 rounded-xl border border-line bg-paper p-4 md:grid-cols-[1.5fr_1fr_1fr_90px_auto]">
              <Field label="Istituto" value={e.institution} onChange={(v) => set({ institution: v })} />
              <Field label="Titolo" value={e.degree} onChange={(v) => set({ degree: v })} />
              <Field label="Ambito" value={e.field} onChange={(v) => set({ field: v })} />
              <Field label="Anno" value={e.year} onChange={(v) => set({ year: v })} />
              <RemoveButton label="Rimuovi titolo" onClick={() => setDraft({ ...draft, education: draft.education.filter((_, j) => j !== i) })} />
            </div>
          );
        })}
        <AddRow label="Aggiungi titolo" onClick={() => setDraft({ ...draft, education: [...draft.education, { institution: "", degree: "", field: "", year: "" }] })} />
      </Card>

      {critique && (
        <details className="rounded-2xl border border-line bg-paper-2 p-5">
          <summary className="cursor-pointer text-sm font-medium">
            Un consiglio sul tuo CV (facoltativo)
          </summary>
          <p className="mt-3 whitespace-pre-wrap text-sm text-ink-soft">{critique}</p>
        </details>
      )}

      <div className="sticky bottom-4 flex items-center justify-between gap-3 rounded-2xl border border-line-hard bg-paper-2 p-4">
        <span className="text-sm text-ink-soft">
          {canCreate ? "Tutto a posto? Potrai modificare ogni cosa anche dopo." : "Servono almeno nome ed email valida."}
        </span>
        <Button size="lg" onClick={handleCreate} disabled={!canCreate || createProfile.isPending}>
          {createProfile.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Crea il mio profilo
        </Button>
      </div>
    </div>
  );
}

/* ----------------------------- pezzi riusabili ---------------------------- */

function ChoiceCard({
  icon, title, text, tag, onClick,
}: { icon: React.ReactNode; title: string; text: string; tag?: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="jm-press group relative flex flex-col items-start gap-3 rounded-2xl border border-line-hard bg-paper-2 p-6 sm:p-7 text-left transition-all hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
    >
      {tag && <Badge className="absolute right-4 top-4">{tag}</Badge>}
      <span className="grid h-12 w-12 place-items-center rounded-full bg-accent-wash text-accent">{icon}</span>
      <span className="jm-h2">{title}</span>
      <span className="text-sm text-ink-soft">{text}</span>
    </button>
  );
}

function BackLink({ onClick, label = "Indietro" }: { onClick: () => void; label?: string }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex h-10 items-center rounded-full text-sm text-ink-soft underline-offset-4 hover:underline">
      ← {label}
    </button>
  );
}

function UploadBox({ onFile, loading }: { onFile: (f: File | undefined) => void; loading: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files[0]); }}
      className={
        "flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed p-8 sm:p-12 text-center transition-colors " +
        (over ? "border-accent bg-accent-wash" : "border-line-hard bg-paper-2")
      }
    >
      <input ref={input} type="file" accept=".pdf,application/pdf" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
      {loading ? (
        <>
          <Loader2 className="h-8 w-8 animate-spin text-accent" />
          <p className="text-ink-soft">Leggo il tuo CV… può volerci mezzo minuto.</p>
        </>
      ) : (
        <>
          <FileUp className="h-8 w-8 text-accent" />
          <p className="font-medium">Trascina qui il PDF</p>
          <p className="text-sm text-ink-faint">oppure</p>
          <Button variant="outline" onClick={() => input.current?.click()}>Scegli un file</Button>
          <p className="text-xs text-ink-faint">Solo PDF con testo selezionabile, max 8 MB.</p>
        </>
      )}
    </div>
  );
}

function Field({
  label, value, onChange, type = "text", placeholder, warn, hint,
}: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string; warn?: boolean; hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={warn ? "border-warn" : undefined}
      />
      {hint && <p className="text-xs text-warn">{hint}</p>}
    </div>
  );
}

function ChipEditor({
  label, items, onChange, placeholder,
}: { label: string; items: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [text, setText] = useState("");
  const add = () => {
    const t = text.trim();
    if (t && !items.some((i) => i.toLowerCase() === t.toLowerCase())) onChange([...items, t]);
    setText("");
  };
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-2">
        {items.map((s) => (
          <Badge key={s} className="gap-1 pr-1">
            {s}
            <button type="button" aria-label={`Rimuovi ${s}`} className="grid h-6 w-6 place-items-center rounded-full hover:bg-paper-2" onClick={() => onChange(items.filter((x) => x !== s))}>
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <Input
        value={text}
        placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
        onBlur={add}
      />
    </div>
  );
}

function RemoveButton({ onClick, label = "Rimuovi" }: { onClick: () => void; label?: string }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} className="jm-press grid h-10 w-10 shrink-0 place-items-center rounded-full text-ink-faint hover:bg-bad-wash hover:text-bad">
      <Trash2 className="h-4 w-4" />
    </button>
  );
}

function AddRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button type="button" variant="outline" size="sm" onClick={onClick}>
      <Plus className="mr-1 h-4 w-4" /> {label}
    </Button>
  );
}

