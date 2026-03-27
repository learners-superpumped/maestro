import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { toast } from "sonner"

export function useDriveStatus() {
  return useQuery({
    queryKey: ["drive-status"],
    queryFn: () => api.drive.status(),
  })
}

export function useDriveAuthUrl() {
  return useMutation({
    mutationFn: (data: { client_id: string; client_secret: string }) =>
      api.drive.authUrl(data),
    onError: (err: Error) => toast.error(err.message),
  })
}

export function useDriveDrives() {
  return useQuery({
    queryKey: ["drive-drives"],
    queryFn: () => api.drive.drives(),
    enabled: false, // manually triggered after connection
  })
}

export function useDriveFolders(params: { drive_id?: string; parent_id?: string }) {
  return useQuery({
    queryKey: ["drive-folders", params],
    queryFn: () => api.drive.folders(params),
    enabled: params.drive_id !== undefined,
  })
}

export function useDriveSetup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { drive_id: string; root_folder_id: string }) =>
      api.drive.setup(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drive-status"] })
      toast.success("Drive settings saved")
    },
    onError: (err: Error) => toast.error(err.message),
  })
}
