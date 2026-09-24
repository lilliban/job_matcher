/**
 * Stato globale minimale: identita utente + sessione selezionata.
 * Persistente in localStorage per sopravvivere al refresh (chiavi come nella
 * vecchia SPA: `jm.userId`, `jm.sessionId`).
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface AppState {
  userId: string | null;
  sessionId: string | null;
  setUserId: (id: string | null) => void;
  setSessionId: (id: string | null) => void;
  reset: () => void;
}

export const useAppState = create<AppState>()(
  persist(
    (set) => ({
      userId: null,
      sessionId: null,
      setUserId: (id) => set({ userId: id }),
      setSessionId: (id) => set({ sessionId: id }),
      reset: () => set({ userId: null, sessionId: null }),
    }),
    {
      name: "jm.app-state",
      storage: createJSONStorage(() => localStorage),
      // Retro-compat: se esistono le vecchie chiavi flat, le migriamo al primo boot.
      migrate: (persisted) => persisted as AppState,
      partialize: (s) => ({ userId: s.userId, sessionId: s.sessionId }) as AppState,
    },
  ),
);

// Migrazione una-tantum dai vecchi localStorage flat (jm.userId, jm.sessionId).
if (typeof window !== "undefined") {
  const legacyUserId = localStorage.getItem("jm.userId");
  const legacySessionId = localStorage.getItem("jm.sessionId");
  const current = useAppState.getState();
  if (legacyUserId && !current.userId) useAppState.getState().setUserId(legacyUserId);
  if (legacySessionId && !current.sessionId) useAppState.getState().setSessionId(legacySessionId);
}
