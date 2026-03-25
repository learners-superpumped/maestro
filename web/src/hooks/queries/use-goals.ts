import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { toast } from "sonner"

export function useGoals() {
  return useQuery({
    queryKey: ["goals"],
    queryFn: () => api.goals.list(),
  })
}

export function useCreateGoal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.goals.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] })
      toast.success("Goal created")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useDeleteGoal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.goals.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] })
      toast.success("Goal deleted")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useToggleGoal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      enabled ? api.goals.enable(id) : api.goals.disable(id),
    onSuccess: (_data, { enabled }) => {
      queryClient.invalidateQueries({ queryKey: ["goals"] })
      toast.success(enabled ? "Goal enabled" : "Goal disabled")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}
