import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Trash2, Loader2 } from "lucide-react"
import {
  useSchedules,
  useCreateSchedule,
  useDeleteSchedule,
  useToggleSchedule,
} from "@/hooks/queries/use-schedules"
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

const scheduleSchema = z.object({
  name: z.string().min(1, "Required"),
  workspace: z.string().min(1, "Required"),
  task_type: z.string().min(1, "Required"),
  cron: z.string(),
  interval_ms: z.number().int().min(0),
  approval_level: z.string(),
})

type ScheduleFormValues = z.infer<typeof scheduleSchema>

export function Schedules() {
  const [open, setOpen] = useState(false)

  const { data, isLoading } = useSchedules()
  const createSchedule = useCreateSchedule()
  const deleteSchedule = useDeleteSchedule()
  const toggleSchedule = useToggleSchedule()

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<ScheduleFormValues>({
    resolver: zodResolver(scheduleSchema),
    defaultValues: { interval_ms: 0, approval_level: "none", cron: "" },
  })

  const onSubmit = handleSubmit(async (values) => {
    const payload: any = {
      name: values.name,
      workspace: values.workspace,
      task_type: values.task_type,
      approval_level: values.approval_level,
    }
    if (values.cron) payload.cron = values.cron
    if (values.interval_ms) payload.interval_ms = values.interval_ms
    await createSchedule.mutateAsync(payload)
    reset()
    setOpen(false)
  })

  const schedules: any[] = data?.schedules ?? []

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-50">Schedules</h1>
          <p className="text-sm text-gray-400 mt-1">
            {data?.count != null ? `${data.count} schedules` : ""}
          </p>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="bg-indigo-600 hover:bg-indigo-500 text-white">
                <Plus className="h-4 w-4 mr-1" />
                Add Schedule
              </Button>
            }
          />
          <DialogContent className="bg-gray-900 border-gray-800 text-gray-50 max-w-lg">
            <DialogHeader>
              <DialogTitle>Add Schedule</DialogTitle>
            </DialogHeader>
            <form onSubmit={onSubmit} className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Name *</Label>
                  <Input
                    {...register("name")}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                  />
                  {errors.name && (
                    <p className="text-xs text-red-400">{errors.name.message}</p>
                  )}
                </div>
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

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Cron Expression</Label>
                  <Input
                    {...register("cron")}
                    className="bg-gray-800 border-gray-700 text-gray-50 font-mono"
                    placeholder="0 * * * *"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Interval (ms)</Label>
                  <Input
                    type="number"
                    {...register("interval_ms", { valueAsNumber: true })}
                    className="bg-gray-800 border-gray-700 text-gray-50"
                    placeholder="0"
                  />
                </div>
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
                  disabled={createSchedule.isPending}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white"
                >
                  {createSchedule.isPending && (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  )}
                  Create
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-gray-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-800 hover:bg-transparent">
              <TableHead className="text-gray-400 text-xs">Name</TableHead>
              <TableHead className="text-gray-400 text-xs">Workspace</TableHead>
              <TableHead className="text-gray-400 text-xs">Task Type</TableHead>
              <TableHead className="text-gray-400 text-xs">Trigger</TableHead>
              <TableHead className="text-gray-400 text-xs">Enabled</TableHead>
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
              : schedules.map((s: any) => (
                  <TableRow key={s.name} className="border-gray-800 hover:bg-gray-800/30">
                    <TableCell className="text-gray-50 text-sm font-medium">
                      {s.name}
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm">{s.workspace}</TableCell>
                    <TableCell className="text-gray-400 text-sm font-mono text-xs">
                      {s.task_type}
                    </TableCell>
                    <TableCell className="text-gray-400 text-xs font-mono">
                      {s.cron
                        ? s.cron
                        : s.interval_ms
                        ? `${s.interval_ms}ms`
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Switch
                        checked={!!s.enabled}
                        onCheckedChange={(checked) =>
                          toggleSchedule.mutate({ name: s.name, enabled: checked })
                        }
                        disabled={toggleSchedule.isPending}
                        className="data-[state=checked]:bg-indigo-500"
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => deleteSchedule.mutate(s.name)}
                        disabled={deleteSchedule.isPending}
                        className="h-7 w-7 text-gray-500 hover:text-red-400"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && schedules.length === 0 && (
              <TableRow className="border-gray-800">
                <TableCell colSpan={6} className="text-center text-gray-500 py-8">
                  No schedules found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
