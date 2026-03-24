import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Loader2, ChevronDown, ChevronUp } from "lucide-react"
import { useRootTasks, useCreateTask } from "@/hooks/queries/use-tasks"
import { useWorkspaces } from "@/hooks/queries/use-workspaces"
import { ActionRequired } from "@/components/ActionRequired"
import { TaskBoard } from "@/components/TaskBoard"
import { TaskListTree } from "@/components/TaskListTree"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
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

const taskSchema = z.object({
  workspace: z.string().min(1, "Required"),
  title: z.string().min(1, "Required"),
  instruction: z.string().min(1, "Required"),
  priority: z.number().int().min(0).max(100),
  approval_level: z.number().int().min(0).max(2),
  budget_usd: z.number().min(0).optional(),
  max_retries: z.number().int().min(0).optional(),
  parent_task_id: z.string().optional(),
  goal_id: z.string().optional(),
})

const APPROVAL_LEVELS = [
  { value: "0", label: "Auto-run" },
  { value: "1", label: "Notify after" },
  { value: "2", label: "Require approval" },
]

const PRIORITY_PRESETS = [
  { value: "1", label: "Urgent" },
  { value: "2", label: "High" },
  { value: "3", label: "Normal" },
  { value: "5", label: "Low" },
]

type TaskFormValues = z.infer<typeof taskSchema>

export function Tasks() {
  const [view, setView] = useState<"list" | "board">("list")
  const [statusFilter, setStatusFilter] = useState("")
  const [workspaceFilter, setWorkspaceFilter] = useState("")
  const [showSystem, setShowSystem] = useState(false)
  const [open, setOpen] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const { data, isLoading } = useRootTasks({
    status: statusFilter || undefined,
    workspace: workspaceFilter || undefined,
  })

  const { data: wsData } = useWorkspaces()
  const workspaces: any[] = wsData?.workspaces ?? []

  const createTask = useCreateTask()

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<TaskFormValues>({
    resolver: zodResolver(taskSchema),
    defaultValues: { priority: 3, approval_level: 2 },
  })

  const onSubmit = handleSubmit(async (values) => {
    const payload: any = {
      workspace: values.workspace,
      type: "claude",
      title: values.title,
      instruction: values.instruction,
      priority: values.priority,
      approval_level: values.approval_level,
    }
    if (values.budget_usd) payload.budget_usd = values.budget_usd
    if (values.max_retries) payload.max_retries = values.max_retries
    if (values.parent_task_id?.trim()) payload.parent_task_id = values.parent_task_id.trim()
    if (values.goal_id?.trim()) payload.goal_id = values.goal_id.trim()
    await createTask.mutateAsync(payload)
    reset()
    setOpen(false)
  })

  const allTasks: any[] = data?.tasks ?? []
  // Filter out system workspaces unless toggled on
  const tasks = showSystem ? allTasks : allTasks.filter((t: any) =>
    !t.workspace?.startsWith("_")
  )

  return (
    <div className="space-y-6">
      {/* Header + New Task button */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-[#37352f]">Tasks</h1>
          <p className="text-[14px] text-[#787774] mt-1">
            {tasks.length} {tasks.length === 1 ? "task" : "tasks"}
            {tasks.length > 0 && (() => {
              const done = tasks.filter((t: any) => t.status === "completed").length
              const failed = tasks.filter((t: any) => t.status === "failed").length
              const running = tasks.filter((t: any) => t.status === "running").length
              const parts = []
              if (running > 0) parts.push(`${running} running`)
              if (done > 0) parts.push(`${done} done`)
              if (failed > 0) parts.push(`${failed} failed`)
              return parts.length > 0 ? ` · ${parts.join(" · ")}` : ""
            })()}
          </p>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="bg-[#2383e2] hover:bg-[#1a73cc] text-white h-[32px] text-[13px] rounded px-3">
                <Plus className="h-4 w-4 mr-1" />
                New Task
              </Button>
            }
          />
          <DialogContent className="bg-white border border-[#e8e5df] max-w-lg">
            <DialogHeader>
              <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Create Task</DialogTitle>
            </DialogHeader>
            <form onSubmit={onSubmit} className="space-y-4 mt-2">
              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Workspace *</Label>
                <Select onValueChange={(v) => setValue("workspace", v)}>
                  <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]">
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
                <Label className="text-[12px] text-[#9b9a97]">Title *</Label>
                <Input
                  {...register("title")}
                  className="bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]"
                />
                {errors.title && (
                  <p className="text-[12px] text-[#eb5757]">{errors.title.message}</p>
                )}
              </div>

              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Instruction *</Label>
                <Textarea
                  {...register("instruction")}
                  className="bg-white border-[#e8e5df] text-[#37352f] min-h-24 text-[13px]"
                />
                {errors.instruction && (
                  <p className="text-[12px] text-[#eb5757]">{errors.instruction.message}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Priority</Label>
                  <Select defaultValue="3" onValueChange={(v) => setValue("priority", Number(v))}>
                    <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]">
                      <SelectValue placeholder="Select priority" />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-[#e8e5df]">
                      {PRIORITY_PRESETS.map((p) => (
                        <SelectItem key={p.value} value={p.value} className="text-[13px] text-[#37352f] hover:bg-[#f7f6f3]">
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">When to run</Label>
                  <Select defaultValue="2" onValueChange={(v) => setValue("approval_level", Number(v))}>
                    <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-[#e8e5df]">
                      {APPROVAL_LEVELS.map((level) => (
                        <SelectItem key={level.value} value={level.value} className="text-[13px] text-[#37352f] hover:bg-[#f7f6f3]">
                          {level.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <button
                  type="button"
                  onClick={() => setShowAdvanced((v) => !v)}
                  className="flex items-center gap-1 text-[12px] text-[#9b9a97] hover:text-[#37352f] transition-colors"
                >
                  {showAdvanced ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                  Advanced options
                </button>

                {showAdvanced && (
                  <div className="mt-3 space-y-3">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <Label className="text-[12px] text-[#9b9a97]">Budget (USD)</Label>
                        <Input
                          type="number"
                          step="0.01"
                          {...register("budget_usd", { valueAsNumber: true })}
                          className="bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]"
                          placeholder="5.00"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-[12px] text-[#9b9a97]">Max Retries</Label>
                        <Input
                          type="number"
                          {...register("max_retries", { valueAsNumber: true })}
                          className="bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]"
                          placeholder="3"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <Label className="text-[12px] text-[#9b9a97]">Parent Task ID</Label>
                        <Input
                          {...register("parent_task_id")}
                          className="bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]"
                          placeholder="Optional"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-[12px] text-[#9b9a97]">Goal ID</Label>
                        <Input
                          {...register("goal_id")}
                          className="bg-white border-[#e8e5df] text-[#37352f] h-[32px] text-[13px]"
                          placeholder="Optional"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setOpen(false)}
                  className="text-[#787774] hover:bg-[#f7f6f3]"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createTask.isPending}
                  className="bg-[#2383e2] hover:bg-[#1a73cc] text-white h-[32px] text-[13px]"
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

      {/* Action Required section */}
      <ActionRequired />

      {/* View toggle + Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Tabs value={view} onValueChange={(v) => setView(v as "list" | "board")}>
          <TabsList className="bg-white border border-[#e8e5df] rounded p-0.5 h-auto">
            <TabsTrigger
              value="list"
              className="text-[13px] h-[28px] px-3 data-[state=active]:bg-[#f7f6f3] data-[state=active]:text-[#37352f] data-[state=inactive]:text-[#9b9a97]"
            >
              List
            </TabsTrigger>
            <TabsTrigger
              value="board"
              className="text-[13px] h-[28px] px-3 data-[state=active]:bg-[#f7f6f3] data-[state=active]:text-[#37352f] data-[state=inactive]:text-[#9b9a97]"
            >
              Board
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex items-center gap-1.5">
          <span className="text-[12px] text-[#9b9a97] font-medium">Status</span>
          <Select value={statusFilter || "all"} onValueChange={(v) => setStatusFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="w-36 bg-white border-[#e8e5df] text-[#37352f] text-[13px] h-[32px]">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent className="bg-white border border-[#e8e5df]">
              <SelectItem value="all" className="text-[#37352f] hover:bg-[#f7f6f3] text-[13px]">All statuses</SelectItem>
              {["pending", "running", "paused", "completed", "failed"].map((s) => (
                <SelectItem key={s} value={s} className="text-[#37352f] hover:bg-[#f7f6f3] text-[13px] capitalize">{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[12px] text-[#9b9a97] font-medium">Workspace</span>
          <Select value={workspaceFilter || "all"} onValueChange={(v) => setWorkspaceFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="w-40 bg-white border-[#e8e5df] text-[#37352f] text-[13px] h-[32px]">
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

        <div className="flex items-center gap-2">
          <Switch checked={showSystem} onCheckedChange={setShowSystem} />
          <span className="text-[12px] text-[#9b9a97]">System</span>
        </div>
      </div>

      {/* View content */}
      {view === "board" ? (
        <TaskBoard tasks={tasks} />
      ) : (
        <TaskListTree tasks={tasks} isLoading={isLoading} />
      )}
    </div>
  )
}
