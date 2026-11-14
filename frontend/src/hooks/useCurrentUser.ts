/**
 * Bootstrap dell'utente corrente: se lo store ha un userId lo usa, altrimenti
 * ripiega sul primo utente esistente (retro-compat col vecchio localStorage).
 * Se il DB è vuoto, restituisce `{ userId: null, user: null }` cosicché la UI
 * possa mostrare il form di creazione.
 */

import { useEffect } from "react";
import { useUser, useUsers } from "@/api/queries";
import { useAppState } from "@/stores/useAppState";

export function useCurrentUser() {
  const userId = useAppState((s) => s.userId);
  const setUserId = useAppState((s) => s.setUserId);

  const usersQuery = useUsers();
  const userQuery = useUser(userId);

  // Se lo store ha uno userId ma il fetch ritorna 404, invalido e ripiega sul primo.
  useEffect(() => {
    if (userQuery.isError && userId) {
      setUserId(null);
    }
  }, [userQuery.isError, userId, setUserId]);

  // Se nessun userId ma esistono utenti, prendo il primo (retro-compat legacy DB).
  useEffect(() => {
    if (!userId && usersQuery.data && usersQuery.data.length > 0) {
      setUserId(usersQuery.data[0].id);
    }
  }, [userId, usersQuery.data, setUserId]);

  const isBooting = usersQuery.isLoading || (!!userId && userQuery.isLoading);

  return {
    userId,
    user: userQuery.data ?? null,
    isBooting,
    hasAnyUser: !!(usersQuery.data && usersQuery.data.length > 0),
  };
}
