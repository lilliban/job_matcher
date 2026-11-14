import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ProfileView } from "@/views/ProfileView";
import { CompaniesView } from "@/views/CompaniesView";
import { SessionsView } from "@/views/SessionsView";
import { ReportView } from "@/views/ReportView";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/profile" replace /> },
      { path: "profile", element: <ProfileView /> },
      { path: "collections", element: <CompaniesView /> },
      { path: "sessions", element: <SessionsView /> },
      { path: "intelligence", element: <ReportView /> },
    ],
  },
]);
