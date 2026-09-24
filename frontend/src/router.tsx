import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ProfileView } from "@/views/ProfileView";
import { CollectionsView } from "@/views/CollectionsView";
import { SessionsView } from "@/views/SessionsView";
import { IntelligenceView } from "@/views/IntelligenceView";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/profile" replace /> },
      { path: "profile", element: <ProfileView /> },
      { path: "collections", element: <CollectionsView /> },
      { path: "sessions", element: <SessionsView /> },
      { path: "intelligence", element: <IntelligenceView /> },
    ],
  },
]);
