import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Trash2, Loader2 } from "lucide-react"
import { useRules, useCreateRule, useDeleteRule } from "@/hooks/queries/use-rules"
import { useWorkspaces } from "@/hooks/queries/use-workspaces"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
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

const TASK_TYPES = [
  { value: "claude", label: "Claude (AI Agent)" },
  { value: "content_creation", label: "Content Creation" },
  { value: "content_strategy", label: "Content Strategy" },
  { value: "planning", label: "Planning" },
  { value: "review", label: "Review" },
]

const ASSET_TYPES = [
  { value: "post", label: "Post" },
  { value: "document", label: "Document" },
  { value: "image", label: "Image" },
  { value: "video", label: "Video" },
  { value: "audio", label: "Audio" },
  { value: "engage", label: "Engage" },
  { value: "research", label: "Research" },
]

const ruleSchema = z.object({
  workspace: z.string().min(1, "Required"),
  task_type: z.string().min(1, "Required"),
  asset_type: z.string().min(1, "Required"),
  title_field: z.string().min(1, "Required"),
  iterate: z.boolean(),
  tags_from: z.string(),
})

type RuleFormValues = z.infer<typeof ruleSchema>

export function Rules() {
  const [workspaceFilter, setWorkspaceFilter] = useState("")
  const [open, setOpen] = useState(false)

  const { data, isLoading } = useRules({
    workspace: workspaceFilter || undefined,
  })

  const createRule = useCreateRule()
  const deleteRule = useDeleteRule()

  const { data: wsData } = useWorkspaces()
  const workspaces: any[] = wsData?.workspaces ?? []

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<RuleFormValues>({
    resolver: zodResolver(ruleSchema),
    defaultValues: { iterate: false, tags_from: "" },
  })

  const iterateValue = watch("iterate")

  const onSubmit = handleSubmit(async (values) => {
    const tags_from = values.tags_from
      ? values.tags_from.split(",").map((t) => t.trim()).filter(Boolean)
      : []
    await createRule.mutateAsync({ ...values, tags_from })
    reset()
    setOpen(false)
  })

  const rules: any[] = data?.rules ?? []

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-[#37352f]">Rules</h1>
          <p className="text-[14px] text-[#787774] mt-1">
            {data?.count != null ? `${data.count} rules` : ""}
          </p>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3">
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Rule
              </Button>
            }
          />
          <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-lg">
            <DialogHeader>
              <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Add Rule</DialogTitle>
            </DialogHeader>
            <form onSubmit={onSubmit} className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Workspace *</Label>
                  <Select onValueChange={(v) => setValue("workspace", v)}>
                    <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded">
                      <SelectValue placeholder="Select workspace" />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-[#e8e5df]">
                      {workspaces.map((ws: any) => (
                        <SelectItem key={ws.name} value={ws.name} className="text-[#37352f] text-[13px] hover:bg-[#f7f6f3]">
                          {ws.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.workspace && (
                    <p className="text-[12px] text-[#eb5757]">{errors.workspace.message}</p>
                  )}
                </div>
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Task Type *</Label>
                  <Select onValueChange={(v) => setValue("task_type", v)}>
                    <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded">
                      <SelectValue placeholder="Select task type" />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-[#e8e5df]">
                      {TASK_TYPES.map((t) => (
                        <SelectItem key={t.value} value={t.value} className="text-[#37352f] text-[13px] hover:bg-[#f7f6f3]">
                          {t.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.task_type && (
                    <p className="text-[12px] text-[#eb5757]">{errors.task_type.message}</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Asset Type *</Label>
                  <Select onValueChange={(v) => setValue("asset_type", v)}>
                    <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded">
                      <SelectValue placeholder="Select asset type" />
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
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Title Field *</Label>
                  <Input
                    {...register("title_field")}
                    className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                    placeholder="title"
                  />
                  {errors.title_field && (
                    <p className="text-[12px] text-[#eb5757]">{errors.title_field.message}</p>
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Tags From (comma-separated fields)</Label>
                <Input
                  {...register("tags_from")}
                  className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                  placeholder="field1, field2"
                />
              </div>

              <div className="flex items-center gap-3">
                <Switch
                  checked={iterateValue}
                  onCheckedChange={(checked) => setValue("iterate", checked)}
                  className="data-[state=checked]:bg-[#2383e2]"
                />
                <Label className="text-[12px] text-[#9b9a97]">Iterate over asset list</Label>
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
                  disabled={createRule.isPending}
                  className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3"
                >
                  {createRule.isPending && (
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  )}
                  Create
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filter */}
      <div className="flex gap-3">
        <Select value={workspaceFilter || "all"} onValueChange={(v) => setWorkspaceFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-52 bg-[#f7f6f3] border-[#e8e5df] text-[#37352f] text-[13px] h-[32px]">
            <SelectValue placeholder="All workspaces" />
          </SelectTrigger>
          <SelectContent className="bg-white border-[#e8e5df]">
            <SelectItem value="all" className="text-[#37352f] hover:bg-[#f7f6f3] text-[13px]">All workspaces</SelectItem>
            {workspaces.map((ws: any) => (
              <SelectItem key={ws.name} value={ws.name} className="text-[#37352f] hover:bg-[#f7f6f3] text-[13px]">
                {ws.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded border border-[#e8e5df] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Workspace</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Task Type</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Asset Type</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Title Field</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Iterate</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-12">Del</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i} className="border-[#e8e5df]">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-[#f7f6f3]" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : rules.map((rule: any) => (
                  <TableRow
                    key={`${rule.workspace}-${rule.task_type}`}
                    className="border-b border-[#e8e5df] hover:bg-[#f7f6f3]"
                  >
                    <TableCell className="text-[#37352f] text-[14px]">{rule.workspace}</TableCell>
                    <TableCell className="font-mono text-[13px] text-[#787774]">
                      {rule.task_type}
                    </TableCell>
                    <TableCell className="font-mono text-[13px] text-[#787774]">
                      {rule.asset_type}
                    </TableCell>
                    <TableCell className="text-[14px] text-[#787774]">{rule.title_field}</TableCell>
                    <TableCell className="text-[14px] text-[#787774]">
                      {rule.iterate ? "Yes" : "No"}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() =>
                          deleteRule.mutate({
                            workspace: rule.workspace,
                            taskType: rule.task_type,
                          })
                        }
                        disabled={deleteRule.isPending}
                        className="h-7 w-7 text-[#9b9a97] hover:text-[#eb5757] hover:bg-red-50"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && rules.length === 0 && (
              <TableRow className="border-[#e8e5df]">
                <TableCell colSpan={6} className="text-center text-[14px] text-[#9b9a97] py-8">
                  No rules found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
