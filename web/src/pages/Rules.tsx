import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Trash2, Loader2 } from "lucide-react"
import { useRules, useCreateRule, useDeleteRule } from "@/hooks/queries/use-rules"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
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
          <h1 className="text-xl font-semibold text-gray-50">Rules</h1>
          <p className="text-sm text-gray-400 mt-1">
            {data?.count != null ? `${data.count} rules` : ""}
          </p>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="bg-indigo-600 hover:bg-indigo-500 text-white">
                <Plus className="h-4 w-4 mr-1" />
                Add Rule
              </Button>
            }
          />
          <DialogContent className="bg-gray-900 border-gray-800 text-gray-50 max-w-lg">
            <DialogHeader>
              <DialogTitle>Add Rule</DialogTitle>
            </DialogHeader>
            <form onSubmit={onSubmit} className="space-y-4 mt-2">
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
                  <Label className="text-gray-400 text-xs">Task Type *</Label>
                  <Input
                    {...register("task_type")}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                  />
                  {errors.task_type && (
                    <p className="text-xs text-red-400">{errors.task_type.message}</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Asset Type *</Label>
                  <Input
                    {...register("asset_type")}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                  />
                  {errors.asset_type && (
                    <p className="text-xs text-red-400">{errors.asset_type.message}</p>
                  )}
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Title Field *</Label>
                  <Input
                    {...register("title_field")}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                    placeholder="title"
                  />
                  {errors.title_field && (
                    <p className="text-xs text-red-400">{errors.title_field.message}</p>
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-gray-400 text-xs">Tags From (comma-separated fields)</Label>
                <Input
                  {...register("tags_from")}
                  className="bg-gray-800 border-gray-700 text-gray-50"
                  placeholder="field1, field2"
                />
              </div>

              <div className="flex items-center gap-3">
                <Switch
                  checked={iterateValue}
                  onCheckedChange={(checked) => setValue("iterate", checked)}
                  className="data-[state=checked]:bg-indigo-500"
                />
                <Label className="text-gray-400 text-xs">Iterate over asset list</Label>
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
                  disabled={createRule.isPending}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white"
                >
                  {createRule.isPending && (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
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
              <TableHead className="text-gray-400 text-xs">Workspace</TableHead>
              <TableHead className="text-gray-400 text-xs">Task Type</TableHead>
              <TableHead className="text-gray-400 text-xs">Asset Type</TableHead>
              <TableHead className="text-gray-400 text-xs">Title Field</TableHead>
              <TableHead className="text-gray-400 text-xs">Iterate</TableHead>
              <TableHead className="text-gray-400 text-xs w-12">Del</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i} className="border-gray-800">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-gray-800" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : rules.map((rule: any) => (
                  <TableRow
                    key={`${rule.workspace}-${rule.task_type}`}
                    className="border-gray-800 hover:bg-gray-800/30"
                  >
                    <TableCell className="text-gray-50 text-sm">{rule.workspace}</TableCell>
                    <TableCell className="text-gray-400 text-xs font-mono">
                      {rule.task_type}
                    </TableCell>
                    <TableCell className="text-gray-400 text-xs font-mono">
                      {rule.asset_type}
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm">{rule.title_field}</TableCell>
                    <TableCell className="text-gray-400 text-sm">
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
                        className="h-7 w-7 text-gray-500 hover:text-red-400"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && rules.length === 0 && (
              <TableRow className="border-gray-800">
                <TableCell colSpan={6} className="text-center text-gray-500 py-8">
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
