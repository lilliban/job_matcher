import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

interface HealthResponse {
  status: string;
  llm_primary: "gemini" | "ollama" | string;
  places_enabled: boolean;
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api<HealthResponse>("/api/health"),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
