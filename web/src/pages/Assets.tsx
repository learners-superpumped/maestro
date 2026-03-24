import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Trash2, Archive, Loader2, RefreshCw } from "lucide-react"
import {
  useAssets,
  useRegisterAsset,
  useDeleteAsset,
  useArchiveAsset,
  useCleanupAssets,
} from "@/hooks/queries/use-assets"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"

const assetSchema = z.object({
  title: z.string().min(1, "Required"),
  asset_type: z.string().min(1, "Required"),
  content: z.string().min(1, "Required"),
  workspace: z.string().min(1, "Required"),
  tags: z.string(),
  description: z.string(),
  ttl_days: z.number().int().min(0),
})

type AssetFormValues = z.infer<typeof assetSchema>

export function Assets() {
  const [typeFilter, setTypeFilter] = useState("")
  const [workspaceFilter, setWorkspaceFilter] = useState("")
  const [open, setOpen] = useState(false)
  const [cleanupOpen, setCleanupOpen] = useState(false)
  const [graceDays, setGraceDays] = useState("7")

  const { data, isLoading } = useAssets({
    type: typeFilter || undefined,
    workspace: workspaceFilter || undefined,
  })

  const registerAsset = useRegisterAsset()
  const deleteAsset = useDeleteAsset()
  const archiveAsset = useArchiveAsset()
  const cleanup = useCleanupAssets()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssetFormValues>({
    resolver: zodResolver(assetSchema),
    defaultValues: { ttl_days: 0, tags: "", description: "" },
  })

  const onSubmit = handleSubmit(async (values) => {
    let content_json: any
    try {
      content_json = JSON.parse(values.content)
    } catch {
      content_json = { text: values.content }
    }
    const tags = values.tags
      ? values.tags.split(",").map((t) => t.trim()).filter(Boolean)
      : []
    await registerAsset.mutateAsync({
      ...values,
      content_json,
      tags,
      ttl_days: values.ttl_days || undefined,
    })
    reset()
    setOpen(false)
  })

  const assets: any[] = data?.assets ?? []

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-50">Assets</h1>
          <p className="text-sm text-gray-400 mt-1">
            {data?.count != null ? `${data.count} assets` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCleanupOpen(true)}
            className="border-gray-700 text-gray-400 hover:bg-gray-800"
          >
            <RefreshCw className="h-4 w-4 mr-1" />
            Cleanup
          </Button>

          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger
              render={
                <Button className="bg-indigo-600 hover:bg-indigo-500 text-white">
                  <Plus className="h-4 w-4 mr-1" />
                  Register
                </Button>
              }
            />
            <DialogContent className="bg-gray-900 border-gray-800 text-gray-50 max-w-lg">
              <DialogHeader>
                <DialogTitle>Register Asset</DialogTitle>
              </DialogHeader>
              <form onSubmit={onSubmit} className="space-y-4 mt-2">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label className="text-gray-400 text-xs">Title *</Label>
                    <Input
                      {...register("title")}
                      className="bg-gray-800 border-gray-700 text-gray-50"
                    />
                    {errors.title && (
                      <p className="text-xs text-red-400">{errors.title.message}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-gray-400 text-xs">Asset Type *</Label>
                    <Input
                      {...register("asset_type")}
                      className="bg-gray-800 border-gray-700 text-gray-50"
                      placeholder="document, config..."
                    />
                    {errors.asset_type && (
                      <p className="text-xs text-red-400">{errors.asset_type.message}</p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label className="text-gray-400 text-xs">Workspace *</Label>
                    <Input
                      {...register("workspace")}
                      className="bg-gray-800 border-gray-700 text-gray-50"
                      placeholder="default"
                    />
                    {errors.workspace && (
                      <p className="text-xs text-red-400">{errors.workspace.message}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-gray-400 text-xs">TTL Days (0=forever)</Label>
                    <Input
                      type="number"
                      {...register("ttl_days", { valueAsNumber: true })}
                      className="bg-gray-800 border-gray-700 text-gray-50"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Tags (comma-separated)</Label>
                  <Input
                    {...register("tags")}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                    placeholder="tag1, tag2"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Description</Label>
                  <Input
                    {...register("description")}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Content (JSON or text) *</Label>
                  <Textarea
                    {...register("content")}
                    className="bg-gray-800 border-gray-700 text-gray-50 font-mono text-xs min-h-24"
                    placeholder='{"key": "value"}'
                  />
                  {errors.content && (
                    <p className="text-xs text-red-400">{errors.content.message}</p>
                  )}
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setOpen(false)}
                    className="text-gray-400"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={registerAsset.isPending}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white"
                  >
                    {registerAsset.isPending && (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    )}
                    Register
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <Input
          placeholder="Filter by type..."
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="w-44 bg-gray-900 border-gray-800 text-gray-50 placeholder:text-gray-500"
        />
        <Input
          placeholder="Filter by workspace..."
          value={workspaceFilter}
          onChange={(e) => setWorkspaceFilter(e.target.value)}
          className="w-52 bg-gray-900 border-gray-800 text-gray-50 placeholder:text-gray-500"
        />
      </div>

      {/* Table */}
      <div className="rounded-lg border border-gray-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-800 hover:bg-transparent">
              <TableHead className="text-gray-400 text-xs">Type</TableHead>
              <TableHead className="text-gray-400 text-xs">Title</TableHead>
              <TableHead className="text-gray-400 text-xs">Workspace</TableHead>
              <TableHead className="text-gray-400 text-xs">Tags</TableHead>
              <TableHead className="text-gray-400 text-xs">Created By</TableHead>
              <TableHead className="text-gray-400 text-xs">Created At</TableHead>
              <TableHead className="text-gray-400 text-xs w-20">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i} className="border-gray-800">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-gray-800" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : assets.map((asset: any) => (
                  <TableRow key={asset.id} className="border-gray-800 hover:bg-gray-800/30">
                    <TableCell className="text-gray-400 text-xs font-mono">
                      {asset.asset_type}
                    </TableCell>
                    <TableCell className="text-gray-50 text-sm max-w-xs truncate">
                      {asset.title}
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm">{asset.workspace}</TableCell>
                    <TableCell className="text-gray-400 text-xs">
                      {Array.isArray(asset.tags) ? asset.tags.join(", ") : (asset.tags ?? "—")}
                    </TableCell>
                    <TableCell className="text-gray-400 text-xs font-mono">
                      {asset.created_by ?? "—"}
                    </TableCell>
                    <TableCell className="text-gray-400 text-xs">
                      {asset.created_at
                        ? new Date(asset.created_at).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => archiveAsset.mutate(asset.id)}
                          disabled={archiveAsset.isPending}
                          className="h-7 w-7 text-gray-500 hover:text-amber-400"
                          title="Archive"
                        >
                          <Archive className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => deleteAsset.mutate(asset.id)}
                          disabled={deleteAsset.isPending}
                          className="h-7 w-7 text-gray-500 hover:text-red-400"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && assets.length === 0 && (
              <TableRow className="border-gray-800">
                <TableCell colSpan={7} className="text-center text-gray-500 py-8">
                  No assets found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Cleanup dialog */}
      <Dialog open={cleanupOpen} onOpenChange={setCleanupOpen}>
        <DialogContent className="bg-gray-900 border-gray-800 text-gray-50 max-w-sm">
          <DialogHeader>
            <DialogTitle>Cleanup Assets</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1">
              <Label className="text-gray-400 text-xs">Grace Days</Label>
              <Input
                type="number"
                value={graceDays}
                onChange={(e) => setGraceDays(e.target.value)}
                className="bg-gray-800 border-gray-700 text-gray-50"
              />
              <p className="text-xs text-gray-500">
                Archive/purge assets older than this many days
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setCleanupOpen(false)}
                className="text-gray-400"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  cleanup.mutate(Number(graceDays))
                  setCleanupOpen(false)
                }}
                disabled={cleanup.isPending}
                className="bg-amber-600 hover:bg-amber-500 text-white"
              >
                {cleanup.isPending && (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                )}
                Run Cleanup
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
