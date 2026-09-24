import { useState } from "react";
import { toast } from "sonner";
import { ChevronRight, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  useAddCollectionMember,
  useCollectionMembers,
  useCollections,
  useCreateCollection,
  useDeleteCollection,
  useDeleteCollectionMember,
} from "@/api/queries";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export function CollectionsView() {
  const { userId, isBooting } = useCurrentUser();

  if (isBooting) {
    return <div className="text-ink-faint">Caricamento…</div>;
  }
  if (!userId) {
    return (
      <div className="mx-auto max-w-3xl">
        <Header />
        <Card className="p-8 text-ink-soft">
          Crea prima il tuo profilo (Passo uno) per iniziare a raccogliere aziende.
        </Card>
      </div>
    );
  }

  return <CollectionsInner userId={userId} />;
}

function Header() {
  return (
    <header className="mb-8">
      <p className="mb-2 font-mono text-xs uppercase tracking-widest text-ink-faint">
        Passo due
      </p>
      <h1 className="font-serif text-5xl leading-none">Le tue liste di aziende</h1>
      <p className="mt-4 max-w-2xl text-ink-soft">
        Raggruppa le aziende che ti interessano. Da ogni lista puoi farti suggerire
        aziende simili — più la lista è definita, più i suggerimenti lo sono.
      </p>
    </header>
  );
}

function CollectionsInner({ userId }: { userId: string }) {
  const collectionsQuery = useCollections(userId);
  const createCollection = useCreateCollection(userId);
  const deleteCollection = useDeleteCollection(userId);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

  async function handleCreate() {
    if (!name.trim()) return;
    try {
      const created = await createCollection.mutateAsync({
        name,
        description: description || null,
      });
      setName("");
      setDescription("");
      setOpenId(created.id);
      toast.success("Lista creata");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore creazione");
    }
  }

  const openCollection = collectionsQuery.data?.find((c) => c.id === openId) ?? null;

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <Header />

      <Card className="p-8">
        <h2 className="mb-1 font-serif text-2xl">Nuova lista</h2>
        <p className="mb-4 text-sm text-ink-soft">
          Per tema, per zona, per settore: come preferisci.
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <div className="space-y-1.5">
            <Label>Nome</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Es. Tech nelle Marche"
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Descrizione (facoltativa)</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button
              variant="outline"
              onClick={handleCreate}
              disabled={createCollection.isPending}
            >
              Crea lista
            </Button>
          </div>
        </div>
      </Card>

      <div className="space-y-3">
        {collectionsQuery.isLoading && (
          <div className="text-ink-faint">Carico le liste…</div>
        )}
        {collectionsQuery.data?.length === 0 && (
          <div className="rounded border border-dashed border-line bg-paper-2 p-6 text-sm text-ink-faint">
            Nessuna lista ancora. Creane una qui sopra o parti da un tema.
          </div>
        )}
        {(collectionsQuery.data ?? []).map((c) => (
          <Card key={c.id} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <button
                  type="button"
                  onClick={() => setOpenId((prev) => (prev === c.id ? null : c.id))}
                  className="flex items-center gap-2 text-left"
                >
                  <ChevronRight
                    className={
                      "h-4 w-4 transition-transform " +
                      (openId === c.id ? "rotate-90" : "")
                    }
                  />
                  <span className="font-serif text-xl">{c.name}</span>
                </button>
                {c.description && (
                  <p className="ml-6 mt-1 text-sm text-ink-soft">{c.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => {
                  if (confirm(`Eliminare la lista "${c.name}"?`)) {
                    deleteCollection.mutate(c.id);
                  }
                }}
                className="rounded-sm p-1 text-ink-faint hover:bg-line/50 hover:text-bad"
                aria-label={`Elimina ${c.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </Card>
        ))}
      </div>

      {openCollection && (
        <CollectionDetail userId={userId} collectionId={openCollection.id} name={openCollection.name} />
      )}
    </div>
  );
}

function CollectionDetail({
  userId,
  collectionId,
  name,
}: {
  userId: string;
  collectionId: string;
  name: string;
}) {
  const membersQuery = useCollectionMembers(userId, collectionId);
  const addMember = useAddCollectionMember(userId, collectionId);
  const deleteMember = useDeleteCollectionMember(userId, collectionId);

  const [companyName, setCompanyName] = useState("");

  async function handleAdd() {
    if (!companyName.trim()) return;
    try {
      await addMember.mutateAsync({ name: companyName, added_via: "manual" });
      setCompanyName("");
      toast.success("Azienda aggiunta");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore");
    }
  }

  return (
    <Card className="p-8">
      <header className="mb-4">
        <h2 className="font-serif text-2xl">{name}</h2>
        <p className="mt-1 text-sm text-ink-soft">
          {membersQuery.data?.length ?? 0} aziende
        </p>
      </header>

      <div className="flex gap-2">
        <Input
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          placeholder="Aggiungi un'azienda per nome"
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
        />
        <Button variant="outline" onClick={handleAdd} disabled={addMember.isPending}>
          Aggiungi
        </Button>
      </div>

      <ul className="mt-6 space-y-2">
        {(membersQuery.data ?? []).map((m) => (
          <li
            key={m.id}
            className="flex items-center justify-between rounded-sm border border-line bg-paper-2 px-3 py-2 text-sm"
          >
            <div className="flex items-center gap-2">
              <span className="font-medium">{m.name}</span>
              {m.sector && <Badge variant="outline">{m.sector}</Badge>}
              {m.country && <span className="text-xs text-ink-faint">· {m.country}</span>}
            </div>
            <button
              type="button"
              onClick={() => deleteMember.mutate(m.id)}
              className="rounded-sm p-1 text-ink-faint hover:bg-line/50 hover:text-bad"
              aria-label={`Rimuovi ${m.name}`}
            >
              <X className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
