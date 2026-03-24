import { useState } from "react"
import { useNavigate } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Loader2 } from "lucide-react"
import { useTasks, useCreateTask } from "@/hooks/queries/use-tasks"
import { StatusBadge } from "@/components/StatusBadge"
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

const taskSchema = z.object({
  workspace: z.string().min(1, "Required"),
  type: z.string().min(1, "Required"),
  title: z.string().min(1, "Required"),
  instruction: z.string().min(1, "Required"),
  priority: z.number().int().min(0).max(100),
  approval_level: z.string(),
})

type TaskFormValues = z.infer<typeof taskSchema>

const STATUS_OPTIONS = [
  "running",
  "completed",
  "failed",
  "pending",
  "paused",
  "cancelled",
  "approved",
  "claimed",
  "retry_queued",
]

export function Tasks() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<string>("")
  const [workspaceFilter, setWorkspaceFilter] = useState("")
  const [open, setOpen] = useState(false)

  const { data, isLoading } = useTasks({
    status: statusFilter || undefined,
    workspace: workspaceFilter || undefined,
  })

  const createTask = useCreateTask()

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<TaskFormValues>({
    resolver: zodResolver(taskSchema),
    defaultValues: { priority: 50, approval_level: "none" },
  })

  const onSubmit = handleSubmit(async (values) => {
    await createTask.mutateAsync(values)
    reset()
    setOpen(false)
  })

  const tasks: any[] = data?.tasks ?? []

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-50">Tasks</h1>
          <p className="text-sm text-gray-400 mt-1">
            {data?.count != null ? `${data.count} tasks` : ""}
          </p>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="bg-indigo-600 hover:bg-indigo-500 text-white">
                <Plus className="h-4 w-4 mr-1" />
                New Task
              </Button>
            }
          />
          <DialogContent className="bg-gray-900 border-gray-800 text-gray-50 max-w-lg">
            <DialogHeader>
              <DialogTitle>Create Task</DialogTitle>
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
                  <Label className="text-gray-400 text-xs">Type *</Label>
                  <Input
                    {...register("type")}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                    placeholder="task_type"
                  />
                  {errors.type && (
                    <p className="text-xs text-red-400">{errors.type.message}</p>
                  )}
                </div>
              </div>

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
                <Label className="text-gray-400 text-xs">Instruction *</Label>
                <Textarea
                  {...register("instruction")}
                  className="bg-gray-800 border-gray-700 text-gray-50 min-h-24"
                />
                {errors.instruction && (
                  <p className="text-xs text-red-400">{errors.instruction.message}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Priority (0-100)</Label>
                  <Input
                    type="number"
                    {...register("priority", { valueAsNumber: true })}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Approval Level</Label>
                  <Select
                    defaultValue="none"
                    onValueChange={(v) => setValue("approval_level", v ?? "none")}
                  >
                    <SelectTrigger className="bg-gray-800 border-gray-700 text-gray-50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-gray-800 border-gray-700">
                      {["none", "before_start", "after_complete"].map((v) => (
                        <SelectItem key={v} value={v} className="text-gray-50">
                          {v}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
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
                  disabled={createTask.isPending}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white"
                >
                  {createTask.isPending && (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  )}
                  Create
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v === "all" ? "" : (v ?? ""))}
        >
          <SelectTrigger className="w-44 bg-gray-900 border-gray-800 text-gray-50">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent className="bg-gray-800 border-gray-700">
            <SelectItem value="all" className="text-gray-50">
              All statuses
            </SelectItem>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s} value={s} className="text-gray-50 capitalize">
                {s.replace("_", " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

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
              <TableHead className="text-gray-400 text-xs">Status</TableHead>
              <TableHead className="text-gray-400 text-xs">ID</TableHead>
              <TableHead className="text-gray-400 text-xs">Title</TableHead>
              <TableHead className="text-gray-400 text-xs">Workspace</TableHead>
              <TableHead className="text-gray-400 text-xs">Priority</TableHead>
              <TableHead className="text-gray-400 text-xs">Cost</TableHead>
              <TableHead className="text-gray-400 text-xs">Updated</TableHead>
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
              : tasks.map((task: any) => (
                  <TableRow
                    key={task.id}
                    className="border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                    onClick={() =>
                      navigate({ to: "/tasks/$id", params: { id: String(task.id) } })
                    }
                  >
                    <TableCell>
                      <StatusBadge status={task.status} />
                    </TableCell>
                    <TableCell className="font-mono text-xs text-gray-400">
                      {String(task.id).slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-gray-50 max-w-xs truncate">
                      {task.title}
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm">
                      {task.workspace}
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm">
                      {task.priority ?? "—"}
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm font-mono">
                      {task.cost_usd != null
                        ? `$${Number(task.cost_usd).toFixed(4)}`
                        : "—"}
                    </TableCell>
                    <TableCell className="text-gray-400 text-xs">
                      {task.updated_at
                        ? new Date(task.updated_at).toLocaleString()
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && tasks.length === 0 && (
              <TableRow className="border-gray-800">
                <TableCell
                  colSpan={7}
                  className="text-center text-gray-500 py-8"
                >
                  No tasks found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
