import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ProfileView } from "@/views/ProfileView";
import { CompaniesView } from "@/views/CompaniesView";
import { SessionsView } from "@/views/SessionsView";
import { MatchesView } from "@/views/MatchesView";
import { CandidatureView } from "@/views/CandidatureView";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/match" replace /> },
      { path: "match", element: <MatchesView /> },
      { path: "candidature", element: <CandidatureView /> },
      { path: "ricerche", element: <SessionsView /> },
      { path: "aziende", element: <CompaniesView /> },
      { path: "profilo", element: <ProfileView /> },
      // Lo Storico è diventato la scheda «Ricerche fatte» dentro Ricerche
      { path: "storico", element: <Navigate to="/ricerche?scheda=storico" replace /> },
      // Vecchi indirizzi: restano validi per segnalibri e link salvati.
      { path: "matches", element: <Navigate to="/match" replace /> },
      { path: "sessions", element: <Navigate to="/ricerche" replace /> },
      { path: "collections", element: <Navigate to="/aziende" replace /> },
      { path: "profile", element: <Navigate to="/profilo" replace /> },
      { path: "intelligence", element: <Navigate to="/ricerche?scheda=storico" replace /> },
      { path: "*", element: <Navigate to="/match" replace /> },
    ],
  },
]);
