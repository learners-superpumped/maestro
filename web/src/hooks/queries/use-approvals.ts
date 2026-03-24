import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"

export function useApprovals() {
  return useQuery({
    queryKey: ["approvals"],
    queryFn: () => api.approvals.pending(),
    refetchInterval: 15_000,
  })
}
