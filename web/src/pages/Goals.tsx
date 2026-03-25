import { useState } from "react"
import { Plus, Trash2, Loader2, Target, X } from "lucide-react"
import { useGoals, useCreateGoal, useDeleteGoal, useToggleGoal } from "@/hooks/queries/use-goals"
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

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "\u2014"
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const COOLDOWN_PRESETS = [
  { value: "6", label: "6 hours" },
  { value: "12", label: "12 hours" },
  { value: "24", label: "1 day" },
  { value: "48", label: "2 days" },
  { value: "72", label: "3 days" },
  { value: "168", label: "1 week" },
]

function MetricRow({ label, value, onChangeLabel, onChangeValue, onRemove }: {
  label: string
  value: string
  onChangeLabel: (v: string) => void
  onChangeValue: (v: string) => void
  onRemove: () => void
}) {
  return (
    <div className="flex items-center gap-2">
      <Input
        value={label}
        onChange={(e) => onChangeLabel(e.target.value)}
        className="bg-white border-[#e8e5df] text-[#37352f] text-[13px] rounded flex-1"
        placeholder="e.g. post_frequency"
      />
      <Input
        value={value}
        onChange={(e) => onChangeValue(e.target.value)}
        className="bg-white border-[#e8e5df] text-[#37352f] text-[13px] rounded flex-1"
        placeholder="e.g. 3/week"
      />
      <Button
        type="button"
        size="icon"
        variant="ghost"
        onClick={onRemove}
        className="h-7 w-7 text-[#9b9a97] hover:text-[#eb5757] hover:bg-[#eb5757]/5 shrink-0"
      >
        <X className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

function formatMetrics(raw: string): { key: string; value: string }[] {
  try {
    const obj = typeof raw === "string" ? JSON.parse(raw) : raw
    if (typeof obj === "object" && obj !== null) {
      return Object.entries(obj).map(([key, value]) => ({
        key,
        value: String(value),
      }))
    }
  } catch { /* ignore */ }
  return []
}

function toSlug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
}

export function Goals() {
  const [open, setOpen] = useState(false)
  const [formName, setFormName] = useState("")
  const [formWorkspace, setFormWorkspace] = useState("")
  const [formMetrics, setFormMetrics] = useState<{ key: string; value: string }[]>([])
  const [formFrequency, setFormFrequency] = useState("24")

  const { data, isLoading } = useGoals()
  const createGoal = useCreateGoal()
  const deleteGoal = useDeleteGoal()
  const toggleGoal = useToggleGoal()

  const { data: wsData } = useWorkspaces()
  const workspaces: any[] = wsData?.workspaces ?? []

  const goals: any[] = data?.goals ?? []

  const resetForm = () => {
    setFormName("")
    setFormWorkspace("")
    setFormMetrics([])
    setFormFrequency("24")
  }

  const handleCreate = async () => {
    const metrics: Record<string, string> = {}
    for (const m of formMetrics) {
      if (m.key.trim()) metrics[m.key.trim()] = m.value.trim()
    }
    const id = toSlug(formName)
    await createGoal.mutateAsync({
      id,
      workspace: formWorkspace,
      description: formName,
      metrics,
      cooldown_hours: Number(formFrequency) || 24,
    })
    resetForm()
    setOpen(false)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-[#37352f]">Goals</h1>
          <p className="text-[14px] text-[#787774] mt-1">
            {data?.count != null ? `${data.count} goal${data.count !== 1 ? "s" : ""}` : ""}
          </p>
        </div>

        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) resetForm() }}>
          <DialogTrigger
            render={
              <Button className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3">
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Goal
              </Button>
            }
          />
          <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-md">
            <DialogHeader>
              <DialogTitle className="text-[16px] font-semibold text-[#37352f]">New Goal</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              {/* Goal name — primary input */}
              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Goal *</Label>
                <Input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                  placeholder="Threads brand presence"
                  autoFocus
                />
                {formName && (
                  <p className="text-[12px] text-[#9b9a97]">
                    ID: <span className="font-mono text-[#787774]">{toSlug(formName)}</span>
                  </p>
                )}
              </div>

              {/* Workspace + Frequency */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Workspace *</Label>
                  <Select value={formWorkspace} onValueChange={(v) => setFormWorkspace(v ?? "")}>
                    <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-[#e8e5df]">
                      {workspaces.map((ws: any) => (
                        <SelectItem key={ws.name} value={ws.name} className="text-[#37352f] text-[13px] hover:bg-[#f7f6f3]">
                          {ws.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Evaluate every</Label>
                  <Select value={formFrequency} onValueChange={(v) => setFormFrequency(v ?? "24")}>
                    <SelectTrigger className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-[#e8e5df]">
                      {COOLDOWN_PRESETS.map((p) => (
                        <SelectItem key={p.value} value={p.value} className="text-[#37352f] text-[13px] hover:bg-[#f7f6f3]">
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Metrics — key-value pairs */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-[12px] text-[#9b9a97]">Targets</Label>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setFormMetrics([...formMetrics, { key: "", value: "" }])}
                    className="h-6 text-[12px] text-[#2383e2] hover:bg-[#2383e2]/5 px-2"
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    Add
                  </Button>
                </div>
                {formMetrics.length === 0 ? (
                  <p className="text-[12px] text-[#9b9a97] bg-[#f7f6f3] rounded px-3 py-2">
                    Optional. Help the planner understand what to aim for.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {formMetrics.map((m, i) => (
                      <MetricRow
                        key={i}
                        label={m.key}
                        value={m.value}
                        onChangeLabel={(v) => {
                          const next = [...formMetrics]
                          next[i] = { ...next[i], key: v }
                          setFormMetrics(next)
                        }}
                        onChangeValue={(v) => {
                          const next = [...formMetrics]
                          next[i] = { ...next[i], value: v }
                          setFormMetrics(next)
                        }}
                        onRemove={() => setFormMetrics(formMetrics.filter((_, j) => j !== i))}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => { setOpen(false); resetForm() }}
                  className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3]"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={createGoal.isPending || !formName.trim() || !formWorkspace}
                  className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3"
                >
                  {createGoal.isPending && (
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  )}
                  Create
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Table */}
      <div className="rounded border border-[#e8e5df] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">ID</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Workspace</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Metrics</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Cooldown</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Last Evaluated</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Enabled</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-12">Del</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <TableRow key={i} className="border-[#e8e5df]">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-[#f7f6f3]" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : goals.map((g: any) => {
                  const metrics = formatMetrics(g.metrics)
                  return (
                    <TableRow key={g.id} className="border-b border-[#e8e5df] hover:bg-[#f7f6f3]">
                      <TableCell className="text-[#37352f] text-[14px] font-medium">
                        <div className="flex items-center gap-2">
                          <Target className="h-4 w-4 text-[#9b9a97] shrink-0" />
                          <div className="min-w-0">
                            <div className="truncate">{g.id}</div>
                            {g.description && (
                              <div className="text-[12px] text-[#9b9a97] truncate">{g.description}</div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-[14px] text-[#787774]">{g.workspace}</TableCell>
                      <TableCell>
                        {metrics.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {metrics.map((m) => (
                              <span key={m.key} className="inline-flex items-center text-[12px] bg-[#f7f6f3] text-[#787774] border border-[#e8e5df] rounded px-1.5 py-0.5">
                                <span className="text-[#37352f] font-medium">{m.key}</span>
                                <span className="mx-1 text-[#9b9a97]">=</span>
                                {m.value}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-[12px] text-[#9b9a97]">{"\u2014"}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-[14px] text-[#787774]">{g.cooldown_hours}h</TableCell>
                      <TableCell className="text-[12px] text-[#9b9a97]">
                        {formatRelativeTime(g.last_evaluated_at)}
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={!!g.enabled}
                          onCheckedChange={(checked) =>
                            toggleGoal.mutate({ id: g.id, enabled: checked })
                          }
                          disabled={toggleGoal.isPending}
                          className="data-[state=checked]:bg-[#2383e2]"
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => deleteGoal.mutate(g.id)}
                          disabled={deleteGoal.isPending}
                          className="h-7 w-7 text-[#9b9a97] hover:text-[#eb5757] hover:bg-[#eb5757]/5"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
            {!isLoading && goals.length === 0 && (
              <TableRow className="border-[#e8e5df]">
                <TableCell colSpan={7} className="text-center text-[14px] text-[#9b9a97] py-8">
                  No goals found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
