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
  useSearchAssets,
} from "@/hooks/queries/use-assets"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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

const ASSET_TYPES = [
  { value: "post", label: "Post" },
  { value: "document", label: "Document" },
  { value: "image", label: "Image" },
  { value: "video", label: "Video" },
  { value: "audio", label: "Audio" },
  { value: "engage", label: "Engage" },
  { value: "research", label: "Research" },
]

const assetSchema = z.object({
  title: z.string().min(1, "Required"),
  asset_type: z.string().min(1, "Required"),
  content: z.string().min(1, "Required"),
  tags: z.string(),
  description: z.string(),
  ttl_days: z.number().int().min(0),
})

type AssetFormValues = z.infer<typeof assetSchema>

export function Assets() {
  const [typeFilter, setTypeFilter] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<any[] | null>(null)
  const [open, setOpen] = useState(false)
  const [cleanupOpen, setCleanupOpen] = useState(false)
  const [graceDays, setGraceDays] = useState("7")

  const { data, isLoading } = useAssets({
    type: typeFilter || undefined,
  })

  const registerAsset = useRegisterAsset()
  const deleteAsset = useDeleteAsset()
  const archiveAsset = useArchiveAsset()
  const cleanup = useCleanupAssets()
  const searchAssets = useSearchAssets()

  const {
    register,
    handleSubmit,
    reset,
    setValue,
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
  const displayAssets = searchResults ?? assets

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-[#37352f]">Assets</h1>
          <p className="text-[14px] text-[#787774] mt-1">
            {data?.count != null ? `${data.count} assets` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCleanupOpen(true)}
            className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3] border-[#e8e5df] rounded px-3"
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            Cleanup
          </Button>

          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger
              render={
                <Button className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3">
                  <Plus className="h-3.5 w-3.5 mr-1" />
                  Register
                </Button>
              }
            />
            <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-lg">
              <DialogHeader>
                <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Register Asset</DialogTitle>
              </DialogHeader>
              <form onSubmit={onSubmit} className="space-y-4 mt-2">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label className="text-[12px] text-[#9b9a97]">Title *</Label>
                    <Input
                      {...register("title")}
                      className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                    />
                    {errors.title && (
                      <p className="text-[12px] text-[#eb5757]">{errors.title.message}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[12px] text-[#9b9a97]">Asset Type *</Label>
                    <Select onValueChange={(v) => { if (v) setValue("asset_type", v as string) }}>
                      <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded">
                        <SelectValue placeholder="Select type" />
                      </SelectTrigger>
                      <SelectContent className="bg-white border-[#e8e5df]">
                        {ASSET_TYPES.map((t) => (
                          <SelectItem key={t.value} value={t.value} className="text-[#37352f] text-[13px] hover:bg-[#f7f6f3]">
                            {t.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {errors.asset_type && (
                      <p className="text-[12px] text-[#eb5757]">{errors.asset_type.message}</p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label className="text-[12px] text-[#9b9a97]">Tags (comma-separated)</Label>
                    <Input
                      {...register("tags")}
                      className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                      placeholder="tag1, tag2"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[12px] text-[#9b9a97]">TTL Days (0=forever)</Label>
                    <Input
                      type="number"
                      {...register("ttl_days", { valueAsNumber: true })}
                      className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Description</Label>
                  <Input
                    {...register("description")}
                    className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Content (JSON or text) *</Label>
                  <Textarea
                    {...register("content")}
                    className="bg-white border-[#e8e5df] text-[#37352f] font-mono text-[13px] min-h-24 rounded"
                    placeholder='{"key": "value"}'
                  />
                  {errors.content && (
                    <p className="text-[12px] text-[#eb5757]">{errors.content.message}</p>
                  )}
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setOpen(false)}
                    className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3]"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={registerAsset.isPending}
                    className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3"
                  >
                    {registerAsset.isPending && (
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
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
      <div className="flex gap-3 items-center">
        <Select value={typeFilter || "all"} onValueChange={(v) => setTypeFilter(v === "all" ? "" : (v ?? ""))}>
          <SelectTrigger className="w-44 bg-[#f7f6f3] border-[#e8e5df] text-[#37352f] text-[13px] h-[32px]">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent className="bg-white border-[#e8e5df]">
            <SelectItem value="all" className="text-[#37352f] hover:bg-[#f7f6f3] text-[13px]">All types</SelectItem>
            {ASSET_TYPES.map((t: { value: string; label: string }) => (
              <SelectItem key={t.value} value={t.value} className="text-[#37352f] hover:bg-[#f7f6f3] text-[13px]">
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          placeholder="Semantic search..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && searchQuery.trim()) {
              searchAssets.mutate(
                { query: searchQuery, asset_type: typeFilter || undefined },
                { onSuccess: (data) => setSearchResults(data?.results ?? []) }
              )
            }
          }}
          className="w-64 bg-[#f7f6f3] border-[#e8e5df] text-[#37352f] text-[14px] rounded placeholder:text-[#9b9a97]"
        />
        {searchResults !== null && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => { setSearchResults(null); setSearchQuery("") }}
            className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3]"
          >
            Clear search
          </Button>
        )}
      </div>

      {/* Table */}
      <div className="rounded border border-[#e8e5df] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Type</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Title</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Tags</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Created By</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Created At</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-20">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i} className="border-[#e8e5df]">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-[#f7f6f3]" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : displayAssets.map((asset: any) => (
                  <TableRow key={asset.id} className="border-b border-[#e8e5df] hover:bg-[#f7f6f3]">
                    <TableCell className="text-[#787774] font-mono text-[13px]">
                      {asset.asset_type}
                    </TableCell>
                    <TableCell className="text-[#37352f] text-[14px] max-w-xs truncate">
                      {asset.title}
                    </TableCell>
                    <TableCell className="text-[12px] text-[#9b9a97]">
                      {Array.isArray(asset.tags) ? asset.tags.join(", ") : (asset.tags ?? "—")}
                    </TableCell>
                    <TableCell className="font-mono text-[13px] text-[#9b9a97]">
                      {asset.created_by ?? "—"}
                    </TableCell>
                    <TableCell className="text-[12px] text-[#9b9a97]">
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
                          className="h-7 w-7 text-[#9b9a97] hover:text-[#cb912f] hover:bg-[#f7f6f3]"
                          title="Archive"
                        >
                          <Archive className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => deleteAsset.mutate(asset.id)}
                          disabled={deleteAsset.isPending}
                          className="h-7 w-7 text-[#9b9a97] hover:text-[#eb5757] hover:bg-[#eb5757]/5"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && displayAssets.length === 0 && (
              <TableRow className="border-[#e8e5df]">
                <TableCell colSpan={6} className="text-center text-[14px] text-[#9b9a97] py-8">
                  No assets found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Cleanup dialog */}
      <Dialog open={cleanupOpen} onOpenChange={setCleanupOpen}>
        <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Cleanup Assets</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1">
              <Label className="text-[12px] text-[#9b9a97]">Grace Days</Label>
              <Input
                type="number"
                value={graceDays}
                onChange={(e) => setGraceDays(e.target.value)}
                className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
              />
              <p className="text-[12px] text-[#9b9a97]">
                Archive/purge assets older than this many days
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setCleanupOpen(false)}
                className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3]"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  cleanup.mutate(Number(graceDays))
                  setCleanupOpen(false)
                }}
                disabled={cleanup.isPending}
                className="h-[28px] text-[13px] bg-[#cb912f] hover:bg-[#b8821f] text-white rounded px-3"
              >
                {cleanup.isPending && (
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
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
