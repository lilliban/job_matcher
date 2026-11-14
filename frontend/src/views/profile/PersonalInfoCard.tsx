import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateUser, useUpdateUser } from "@/api/queries";
import { useAppState } from "@/stores/useAppState";
import type { UserOut } from "@/api/schemas";

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

  const [form, setForm] = useState(toForm(user));
  const [dirty, setDirty] = useState(false);

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
          <Label htmlFor="pf-bio">Sintesi professionale</Label>
          <Textarea
            id="pf-bio"
            value={form.bio}
            onChange={(e) => update("bio", e.target.value)}
            placeholder="Due righe su cosa sai fare e che lavoro cerchi."
            rows={3}
          />
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
          {dirty ? "Hai modifiche non salvate." : ""}
        </span>
        <div className="flex items-center gap-2">
          <Button onClick={handleSave} disabled={!canSubmit || saving || !dirty}>
            {user ? "Salva profilo" : "Crea profilo"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
