import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { toast } from "sonner"

export function useTasks(params?: { status?: string; workspace?: string }) {
  return useQuery({
    queryKey: ["tasks", params],
    queryFn: () => api.tasks.list(params),
  })
}

export function useTask(id: string) {
  return useQuery({
    queryKey: ["tasks", id],
    queryFn: () => api.tasks.get(id),
    enabled: !!id,
  })
}

export function useTaskChildren(id: string) {
  return useQuery({
    queryKey: ["tasks", id, "children"],
    queryFn: () => api.tasks.children(id),
    enabled: !!id,
  })
}

export function useCreateTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.tasks.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["stats"] })
      toast.success("Task created")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useApproveTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.tasks.approve(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["tasks", id] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["approvals"] })
      queryClient.invalidateQueries({ queryKey: ["stats"] })
      toast.success("Task approved")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useRejectTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) =>
      api.tasks.reject(id, note),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["tasks", id] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["approvals"] })
      queryClient.invalidateQueries({ queryKey: ["stats"] })
      toast.success("Task rejected")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useReviseTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      api.tasks.revise(id, note),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["tasks", id] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      toast.success("Revision note sent")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}
