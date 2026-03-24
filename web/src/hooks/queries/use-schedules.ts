import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { toast } from "sonner"

export function useSchedules() {
  return useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.schedules.list(),
  })
}

export function useCreateSchedule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.schedules.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] })
      toast.success("Schedule created")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useDeleteSchedule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => api.schedules.delete(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] })
      toast.success("Schedule deleted")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useToggleSchedule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      enabled ? api.schedules.enable(name) : api.schedules.disable(name),
    onSuccess: (_data, { enabled }) => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] })
      toast.success(enabled ? "Schedule enabled" : "Schedule disabled")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}
