import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { toast } from "sonner"

export function useRules(params?: { workspace?: string }) {
  return useQuery({
    queryKey: ["rules", params],
    queryFn: () => api.rules.list(params),
  })
}

export function useCreateRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.rules.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] })
      toast.success("Rule created")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useDeleteRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      workspace,
      taskType,
    }: {
      workspace: string
      taskType: string
    }) => api.rules.delete(workspace, taskType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] })
      toast.success("Rule deleted")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}
