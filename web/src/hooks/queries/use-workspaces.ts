import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { toast } from "sonner"

export function useWorkspaces() {
  return useQuery({
    queryKey: ["workspaces"],
    queryFn: () => api.workspaces.list(),
  })
}

export function useCreateWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; template?: string }) =>
      api.workspaces.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspaces"] })
      toast.success("Workspace created")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useValidateWorkspace() {
  return useMutation({
    mutationFn: (name: string) => api.workspaces.validate(name),
    onError: (err: Error) => toast.error(err.message),
  })
}
