import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"

export function useConductorConversations() {
  return useQuery({
    queryKey: ["conductor-conversations"],
    queryFn: () => api.conductor.conversations(),
    refetchInterval: 15_000,
  })
}
