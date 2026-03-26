import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { toast } from "sonner"

export function useAssets(params?: {
  type?: string
  tags?: string
}) {
  return useQuery({
    queryKey: ["assets", params],
    queryFn: () => api.assets.list(params),
  })
}

export function useAsset(id: string) {
  return useQuery({
    queryKey: ["assets", id],
    queryFn: () => api.assets.get(id),
    enabled: !!id,
  })
}

export function useRegisterAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.assets.register(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] })
      toast.success("Asset registered")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useDeleteAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.assets.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] })
      toast.success("Asset deleted")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useArchiveAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.assets.archive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] })
      toast.success("Asset archived")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useSearchAssets() {
  return useMutation({
    mutationFn: (data: { query: string; asset_type?: string; limit?: number }) =>
      api.assets.search(data),
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useCleanupAssets() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (graceDays: number) => api.assets.cleanup(graceDays),
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["assets"] })
      toast.success(
        `Cleanup done: ${data.archived ?? 0} archived, ${data.purged ?? 0} purged`
      )
    },
    onError: (err: Error) => toast.error(err.message),
  })
}
