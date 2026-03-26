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

const TASK_TYPES = [
  { value: "claude", label: "Claude (AI Agent)" },
  { value: "content_creation", label: "Content Creation" },
  { value: "content_strategy", label: "Content Strategy" },
  { value: "planning", label: "Planning" },
  { value: "review", label: "Review" },
]

const scheduleSchema = z.object({
  name: z.string().min(1, "Required"),
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
          <h1 className="text-[20px] font-semibold text-[#37352f]">Schedules</h1>
          <p className="text-[14px] text-[#787774] mt-1">
            {data?.count != null ? `${data.count} schedules` : ""}
          </p>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3">
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Schedule
              </Button>
            }
          />
          <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-lg">
            <DialogHeader>
              <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Add Schedule</DialogTitle>
            </DialogHeader>
            <form onSubmit={onSubmit} className="space-y-4 mt-2">
              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Name *</Label>
                <Input
                  {...register("name")}
                  className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                />
                {errors.name && (
                  <p className="text-[12px] text-[#eb5757]">{errors.name.message}</p>
                )}
              </div>

              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Task Type *</Label>
                <Select onValueChange={(v) => { if (v) setValue("task_type", v as string) }}>
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

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Cron Expression</Label>
                  <Input
                    {...register("cron")}
                    className="bg-white border-[#e8e5df] text-[#37352f] font-mono text-[13px] rounded"
                    placeholder="0 * * * *"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Interval (ms)</Label>
                  <Input
                    type="number"
                    {...register("interval_ms", { valueAsNumber: true })}
                    className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                    placeholder="0"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Approval Level</Label>
                <Select
                  defaultValue="none"
                  onValueChange={(v) => setValue("approval_level", v ?? "none")}
                >
                  <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-[#e8e5df]">
                    {["none", "before_start", "after_complete"].map((v) => (
                      <SelectItem key={v} value={v} className="text-[#37352f] text-[14px]">
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
                  className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3]"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createSchedule.isPending}
                  className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3"
                >
                  {createSchedule.isPending && (
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  )}
                  Create
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Table */}
      <div className="rounded border border-[#e8e5df] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Name</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Task Type</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Trigger</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Enabled</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-12">Del</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i} className="border-[#e8e5df]">
                    {Array.from({ length: 5 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-[#f7f6f3]" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : schedules.map((s: any) => (
                  <TableRow key={s.name} className="border-b border-[#e8e5df] hover:bg-[#f7f6f3]">
                    <TableCell className="text-[#37352f] text-[14px] font-medium">
                      {s.name}
                    </TableCell>
                    <TableCell className="font-mono text-[13px] text-[#787774]">
                      {s.task_type}
                    </TableCell>
                    <TableCell className="font-mono text-[13px] text-[#9b9a97]">
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
                        className="data-[state=checked]:bg-[#2383e2]"
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => deleteSchedule.mutate(s.name)}
                        disabled={deleteSchedule.isPending}
                        className="h-7 w-7 text-[#9b9a97] hover:text-[#eb5757] hover:bg-[#eb5757]/5"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && schedules.length === 0 && (
              <TableRow className="border-[#e8e5df]">
                <TableCell colSpan={5} className="text-center text-[14px] text-[#9b9a97] py-8">
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
