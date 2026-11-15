/**
 * Stato globale minimale: identita utente + sessione selezionata.
 * Persistente in localStorage per sopravvivere al refresh (chiavi come nella
 * vecchia SPA: `jm.userId`, `jm.sessionId`).
 */

import { create } from "zustand";
import { persist, createJSONStorage, type StateStorage } from "zustand/middleware";

/*
 * localStorage può mancare o lanciare eccezioni (finestra privata, dati del
 * sito bloccati, quota piena). In quei casi l'app deve funzionare lo stesso:
 * ogni accesso passa da qui, e se il browser rifiuta si ripiega su una
 * memoria temporanea che dura finché la scheda resta aperta.
 */
const memory = new Map<string, string>();

function browserStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

const safeStorage: StateStorage = {
  getItem: (key) => {
    try {
      const v = browserStorage()?.getItem(key);
      if (v != null) return v;
    } catch {
      /* ripiego sulla memoria */
    }
    return memory.get(key) ?? null;
  },
  setItem: (key, value) => {
    memory.set(key, value);
    try {
      browserStorage()?.setItem(key, value);
    } catch {
      /* resta solo in memoria */
    }
  },
  removeItem: (key) => {
    memory.delete(key);
    try {
      browserStorage()?.removeItem(key);
    } catch {
      /* niente da fare */
    }
  },
};

/** Solo stringhe, senza doppioni: il valore salvato potrebbe essere stato alterato a mano. */
function cleanIds(v: unknown): string[] {
  return Array.isArray(v) ? [...new Set(v.filter((x): x is string => typeof x === "string"))] : [];
}

interface AppState {
  userId: string | null;
  sessionId: string | null;
  /** ISO: ultima volta che l'utente ha guardato le novità dell'archivio annunci */
  newsSeenAt: string | null;
  /** Ricerche nascoste dallo Storico: solo in questo browser, il DB non cambia */
  hiddenSessionIds: string[];
  hideSessions: (ids: string[]) => void;
  unhideSessions: (ids: string[]) => void;
  markNewsSeen: () => void;
  setUserId: (id: string | null) => void;
  setSessionId: (id: string | null) => void;
  reset: () => void;
}

export const useAppState = create<AppState>()(
  persist(
    (set) => ({
      userId: null,
      sessionId: null,
      newsSeenAt: null,
      hiddenSessionIds: [],
      hideSessions: (ids) =>
        set((s) => ({ hiddenSessionIds: [...new Set([...s.hiddenSessionIds, ...ids])] })),
      unhideSessions: (ids) =>
        set((s) => ({ hiddenSessionIds: s.hiddenSessionIds.filter((x) => !ids.includes(x)) })),
      markNewsSeen: () => set({ newsSeenAt: new Date().toISOString() }),
      setUserId: (id) => set({ userId: id }),
      setSessionId: (id) => set({ sessionId: id }),
      reset: () => set({ userId: null, sessionId: null, newsSeenAt: null, hiddenSessionIds: [] }),
    }),
    {
      name: "jm.app-state",
      storage: createJSONStorage(() => safeStorage),
      // Retro-compat: se esistono le vecchie chiavi flat, le migriamo al primo boot.
      migrate: (persisted) => ({ hiddenSessionIds: [], ...(persisted as object) }) as unknown as AppState,
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<AppState>;
        return { ...current, ...p, hiddenSessionIds: cleanIds(p.hiddenSessionIds) };
      },
      partialize: (s) =>
        ({
          userId: s.userId,
          sessionId: s.sessionId,
          newsSeenAt: s.newsSeenAt,
          hiddenSessionIds: s.hiddenSessionIds,
        }) as AppState,
    },
  ),
);

// Migrazione una-tantum dai vecchi localStorage flat (jm.userId, jm.sessionId).
if (typeof window !== "undefined") {
  const legacyUserId = safeStorage.getItem("jm.userId") as string | null;
  const legacySessionId = safeStorage.getItem("jm.sessionId") as string | null;
  const current = useAppState.getState();
  if (legacyUserId && !current.userId) useAppState.getState().setUserId(legacyUserId);
  if (legacySessionId && !current.sessionId) useAppState.getState().setSessionId(legacySessionId);
}
