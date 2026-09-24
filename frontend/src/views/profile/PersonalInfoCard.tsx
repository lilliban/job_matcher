import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateUser, useParseCv, useUpdateUser } from "@/api/queries";
import { useAppState } from "@/stores/useAppState";
import type { CVParseResult, UserOut } from "@/api/schemas";
import { CVReviewSheet } from "./CVReviewSheet";

interface Props {
  user: UserOut | null;
}

const emptyForm = {
  name: "",
  email: "",
  phone: "",
  location: "",
  bio: "",
  personal_phrase: "",
};

function toForm(u: UserOut | null): typeof emptyForm {
  if (!u) return emptyForm;
  return {
    name: u.name ?? "",
    email: u.email ?? "",
    phone: u.phone ?? "",
    location: u.location ?? "",
    bio: u.bio ?? "",
    personal_phrase: u.personal_phrase ?? "",
  };
}

export function PersonalInfoCard({ user }: Props) {
  const setUserId = useAppState((s) => s.setUserId);
  const createUser = useCreateUser();
  const updateUser = useUpdateUser(user?.id ?? "");
  const parseCv = useParseCv(user?.id ?? "");

  const [form, setForm] = useState(toForm(user));
  const [dirty, setDirty] = useState(false);
  const [cvResult, setCvResult] = useState<CVParseResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setForm(toForm(user));
    setDirty(false);
  }, [user]);

  const update = <K extends keyof typeof form>(key: K, value: string) => {
    setForm((f) => ({ ...f, [key]: value }));
    setDirty(true);
  };

  const canSubmit = !!form.name.trim() && !!form.email.trim();
  const saving = createUser.isPending || updateUser.isPending;

  async function handleCvFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // permette di ricaricare lo stesso file una seconda volta
    if (!file || !user) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Carica un file PDF");
      return;
    }
    try {
      const result = await parseCv.mutateAsync(file);
      setCvResult(result);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Lettura CV fallita");
    }
  }

  async function handleSave() {
    if (!canSubmit) return;
    try {
      if (!user) {
        const created = await createUser.mutateAsync({
          name: form.name,
          email: form.email,
          phone: form.phone || null,
          location: form.location || null,
          bio: form.bio || null,
          personal_phrase: form.personal_phrase || null,
        });
        setUserId(created.id);
        toast.success("Profilo creato");
      } else {
        await updateUser.mutateAsync({
          name: form.name,
          phone: form.phone || null,
          location: form.location || null,
          bio: form.bio || null,
          personal_phrase: form.personal_phrase || null,
        });
        toast.success("Profilo aggiornato");
      }
      setDirty(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore salvataggio");
    }
  }

  return (
    <Card className="p-8">
      <div className="mb-6 flex items-baseline justify-between">
        <h2 className="font-serif text-2xl">Anagrafica</h2>
        {dirty && (
          <span className="font-mono text-xs uppercase tracking-wider text-warn">
            Modifiche non salvate
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="pf-name">Nome e cognome</Label>
          <Input
            id="pf-name"
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            placeholder="Mario Rossi"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pf-email">Email</Label>
          <Input
            id="pf-email"
            type="email"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            placeholder="mario@esempio.it"
            disabled={!!user}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pf-phone">Telefono</Label>
          <Input
            id="pf-phone"
            value={form.phone}
            onChange={(e) => update("phone", e.target.value)}
            placeholder="+39 333 1234567"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pf-location">Dove vivi</Label>
          <Input
            id="pf-location"
            value={form.location}
            onChange={(e) => update("location", e.target.value)}
            placeholder="Civitanova Marche, MC"
          />
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="pf-bio">Chi sei professionalmente</Label>
          <Textarea
            id="pf-bio"
            value={form.bio}
            readOnly
            placeholder="Carica il CV: questa sintesi viene ricavata da lì."
            rows={3}
          />
          <p className="text-xs text-ink-faint">
            Ricavata dal CV base, non si scrive a mano — due righe scritte una volta
            invecchiano, il CV invece lo aggiorni.
          </p>
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="pf-phrase">La tua frase personale per le lettere</Label>
          <Textarea
            id="pf-phrase"
            value={form.personal_phrase}
            onChange={(e) => update("personal_phrase", e.target.value)}
            rows={2}
            placeholder="Mi piacerebbe contribuire al vostro team con le mie competenze tecniche e la mia passione per l'innovazione."
          />
          <p className="text-xs text-ink-faint">
            Questa frase verrà inserita in tutte le tue lettere di presentazione.
          </p>
        </div>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-6">
        <span className="text-xs text-ink-faint">
          {!user && "Salva per attivare le altre sezioni."}
        </span>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={handleCvFile}
          />
          <Button
            variant="outline"
            disabled={saving || !user || parseCv.isPending}
            title={!user ? "Salva il profilo prima di caricare il CV" : undefined}
            onClick={() => fileInputRef.current?.click()}
          >
            {parseCv.isPending ? "Leggo il CV…" : "Carica CV"}
          </Button>
          <Button onClick={handleSave} disabled={!canSubmit || saving || !dirty}>
            {user ? "Salva profilo" : "Crea profilo"}
          </Button>
        </div>
      </div>

      {cvResult && user && (
        <CVReviewSheet userId={user.id} result={cvResult} onClose={() => setCvResult(null)} />
      )}
    </Card>
  );
}
