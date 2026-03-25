import { useState } from "react"
import { Plus, Trash2, Loader2, Target, X } from "lucide-react"
import { useGoals, useCreateGoal, useDeleteGoal, useToggleGoal } from "@/hooks/queries/use-goals"
import { useWorkspaces } from "@/hooks/queries/use-workspaces"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function formatCooldown(h: number): string {
  if (h < 24) return `${h}h`
  if (h === 24) return "Daily"
  if (h < 168) return `${h / 24}d`
  return `${h / 168}w`
}

function toSlug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
}

function parseMetrics(raw: string): { key: string; value: string }[] {
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

const UNIT_OPTIONS = [
  { value: "hours", label: "hours", multiplier: 1 },
  { value: "days", label: "days", multiplier: 24 },
  { value: "weeks", label: "weeks", multiplier: 168 },
]

// ---------------------------------------------------------------------------
// Notion-style property row
// ---------------------------------------------------------------------------

function PropRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center min-h-[34px]">
      <span className="text-[13px] text-[#9b9a97] w-[100px] shrink-0">{label}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function Goals() {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [workspace, setWorkspace] = useState("")
  const [freqAmount, setFreqAmount] = useState(1)
  const [freqUnit, setFreqUnit] = useState("days")
  const [targets, setTargets] = useState<{ key: string; value: string }[]>([])

  const { data, isLoading } = useGoals()
  const createGoal = useCreateGoal()
  const deleteGoal = useDeleteGoal()
  const toggleGoal = useToggleGoal()

  const { data: wsData } = useWorkspaces()
  const workspaces: any[] = wsData?.workspaces ?? []
  const goals: any[] = data?.goals ?? []

  const reset = () => {
    setName("")
    setWorkspace("")
    setFreqAmount(1)
    setFreqUnit("days")
    setTargets([])
  }

  const cooldownHours = freqAmount * (UNIT_OPTIONS.find((u) => u.value === freqUnit)?.multiplier ?? 24)

  const handleCreate = async () => {
    const metrics: Record<string, string> = {}
    for (const t of targets) {
      if (t.key.trim()) metrics[t.key.trim()] = t.value.trim()
    }
    await createGoal.mutateAsync({
      id: toSlug(name),
      workspace,
      description: name,
      metrics,
      cooldown_hours: cooldownHours,
    })
    reset()
    setOpen(false)
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-[#37352f]">Goals</h1>
          <p className="text-[14px] text-[#787774] mt-1">
            {data?.count != null ? `${data.count} goal${data.count !== 1 ? "s" : ""}` : ""}
          </p>
        </div>

        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset() }}>
          <DialogTrigger
            render={
              <Button className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3">
                <Plus className="h-3.5 w-3.5 mr-1" />
                New Goal
              </Button>
            }
          />
          <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-[420px]">
            <DialogHeader>
              <DialogTitle className="text-[16px] font-semibold text-[#37352f]">New Goal</DialogTitle>
            </DialogHeader>

            <div className="mt-3 space-y-1">
              {/* Name — big, prominent, Notion page-title style */}
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="border-0 shadow-none text-[18px] font-medium text-[#37352f] px-0 h-auto py-1 placeholder:text-[#c4c3c0] focus-visible:ring-0"
                placeholder="What do you want to achieve?"
                autoFocus
              />
            </div>

            {/* Properties — Notion inline style */}
            <div className="mt-4 space-y-0 border-t border-[#e8e5df] pt-3">
              <PropRow label="Workspace">
                <Select value={workspace} onValueChange={(v) => setWorkspace(v ?? "")}>
                  <SelectTrigger className="border-0 shadow-none text-[13px] text-[#37352f] h-[34px] px-1.5 rounded hover:bg-[#f7f6f3] focus:ring-0">
                    <SelectValue placeholder="Select workspace..." />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-[#e8e5df]">
                    {workspaces.map((ws: any) => (
                      <SelectItem key={ws.name} value={ws.name} className="text-[#37352f] text-[13px] hover:bg-[#f7f6f3]">
                        {ws.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </PropRow>

              <PropRow label="Check every">
                <div className="flex items-center gap-0.5">
                  <Input
                    type="number"
                    min={1}
                    value={freqAmount}
                    onChange={(e) => setFreqAmount(Math.max(1, Number(e.target.value) || 1))}
                    className="border-0 shadow-none text-[13px] text-[#37352f] h-[34px] w-[44px] rounded text-center px-0 hover:bg-[#f7f6f3] focus-visible:ring-0"
                  />
                  <Select value={freqUnit} onValueChange={(v) => setFreqUnit(v ?? "days")}>
                    <SelectTrigger className="border-0 shadow-none text-[13px] text-[#37352f] h-[34px] w-[76px] rounded hover:bg-[#f7f6f3] focus:ring-0">
                      <SelectValue>{UNIT_OPTIONS.find((u) => u.value === freqUnit)?.label ?? "days"}</SelectValue>
                    </SelectTrigger>
                    <SelectContent className="bg-white border-[#e8e5df]">
                      {UNIT_OPTIONS.map((u) => (
                        <SelectItem key={u.value} value={u.value} className="text-[#37352f] text-[13px] hover:bg-[#f7f6f3]">
                          {u.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </PropRow>
            </div>

            {/* Targets section */}
            <div className="mt-3 border-t border-[#e8e5df] pt-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[13px] text-[#9b9a97]">Targets</span>
                <button
                  type="button"
                  onClick={() => setTargets([...targets, { key: "", value: "" }])}
                  className="text-[12px] text-[#2383e2] hover:underline"
                >
                  + Add target
                </button>
              </div>

              {targets.length === 0 ? (
                <p className="text-[12px] text-[#9b9a97] leading-relaxed">
                  Targets tell the planner what to aim for. For example:<br />
                  <span className="text-[#787774]">Posts per week</span>
                  <span className="text-[#9b9a97]"> = </span>
                  <span className="text-[#787774]">3</span>
                </p>
              ) : (
                <div className="space-y-1.5">
                  {targets.map((t, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <Input
                        value={t.key}
                        onChange={(e) => {
                          const next = [...targets]
                          next[i] = { ...next[i], key: e.target.value }
                          setTargets(next)
                        }}
                        className="border-[#e8e5df] text-[13px] text-[#37352f] rounded h-[30px] flex-1"
                        placeholder="Posts per week"
                      />
                      <span className="text-[12px] text-[#9b9a97]">=</span>
                      <Input
                        value={t.value}
                        onChange={(e) => {
                          const next = [...targets]
                          next[i] = { ...next[i], value: e.target.value }
                          setTargets(next)
                        }}
                        className="border-[#e8e5df] text-[13px] text-[#37352f] rounded h-[30px] w-[80px]"
                        placeholder="3"
                      />
                      <button
                        type="button"
                        onClick={() => setTargets(targets.filter((_, j) => j !== i))}
                        className="text-[#9b9a97] hover:text-[#eb5757] p-0.5"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-[#e8e5df]">
              <Button
                type="button"
                variant="ghost"
                onClick={() => { setOpen(false); reset() }}
                className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3]"
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={createGoal.isPending || !name.trim() || !workspace}
                className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3"
              >
                {createGoal.isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
                Create
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Table */}
      <div className="rounded border border-[#e8e5df] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Goal</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Workspace</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Targets</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Frequency</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Last Run</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Active</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-12"></TableHead>
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
                  const metrics = parseMetrics(g.metrics)
                  return (
                    <TableRow key={g.id} className="border-b border-[#e8e5df] hover:bg-[#f7f6f3]">
                      <TableCell className="text-[14px]">
                        <div className="flex items-center gap-2">
                          <Target className="h-4 w-4 text-[#9b9a97] shrink-0" />
                          <div className="min-w-0">
                            <div className="text-[#37352f] font-medium truncate">
                              {g.description || g.id}
                            </div>
                            {g.description && g.description !== g.id && (
                              <div className="text-[12px] text-[#9b9a97] font-mono truncate">{g.id}</div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-[13px] text-[#787774]">{g.workspace}</TableCell>
                      <TableCell>
                        {metrics.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {metrics.map((m) => (
                              <span key={m.key} className="inline-flex items-center text-[12px] bg-[#f7f6f3] text-[#787774] border border-[#e8e5df] rounded px-1.5 py-0.5">
                                {m.key}
                                <span className="mx-0.5 text-[#9b9a97]">=</span>
                                <span className="text-[#37352f]">{m.value}</span>
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-[12px] text-[#9b9a97]">{"\u2014"}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-[13px] text-[#787774]">
                        {formatCooldown(g.cooldown_hours)}
                      </TableCell>
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
                  No goals yet
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
