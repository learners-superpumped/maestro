import { useState } from "react"
import { Plus, Trash2, Loader2, Target, X, Play, Pencil } from "lucide-react"
import { useGoals, useCreateGoal, useDeleteGoal, useToggleGoal, useTriggerGoal, useUpdateGoal } from "@/hooks/queries/use-goals"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
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

function parseTargets(raw: string): string[] {
  try {
    const obj = typeof raw === "string" ? JSON.parse(raw) : raw
    if (typeof obj === "object" && obj !== null) {
      // New format: { targets: ["..."] }
      if (Array.isArray(obj.targets)) return obj.targets
      // Legacy format: { key: value, ... } → "key: value"
      return Object.entries(obj).map(([k, v]) => `${k}: ${v}`)
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
  const [freqAmount, setFreqAmount] = useState(1)
  const [freqUnit, setFreqUnit] = useState("days")
  const [targets, setTargets] = useState<string[]>([])

  const { data, isLoading } = useGoals()
  const createGoal = useCreateGoal()
  const deleteGoal = useDeleteGoal()
  const toggleGoal = useToggleGoal()
  const triggerGoal = useTriggerGoal()
  const updateGoal = useUpdateGoal()

  const [editGoal, setEditGoal] = useState<any | null>(null)
  const [editName, setEditName] = useState("")
  const [editFreqAmount, setEditFreqAmount] = useState(1)
  const [editFreqUnit, setEditFreqUnit] = useState("days")
  const [editTargets, setEditTargets] = useState<string[]>([])

  const openEdit = (g: any) => {
    setEditGoal(g)
    setEditName(g.description || g.id)
    const h = g.cooldown_hours
    if (h >= 168 && h % 168 === 0) {
      setEditFreqAmount(h / 168)
      setEditFreqUnit("weeks")
    } else if (h >= 24 && h % 24 === 0) {
      setEditFreqAmount(h / 24)
      setEditFreqUnit("days")
    } else {
      setEditFreqAmount(h)
      setEditFreqUnit("hours")
    }
    setEditTargets(parseTargets(g.metrics))
  }

  const editCooldownHours = editFreqAmount * (UNIT_OPTIONS.find((u) => u.value === editFreqUnit)?.multiplier ?? 24)

  const handleUpdate = async () => {
    if (!editGoal) return
    const filteredTargets = editTargets.filter((t) => t.trim())
    await updateGoal.mutateAsync({
      id: editGoal.id,
      description: editName,
      metrics: { targets: filteredTargets },
      cooldown_hours: editCooldownHours,
    })
    setEditGoal(null)
  }

  const goals: any[] = data?.goals ?? []

  const reset = () => {
    setName("")
    setFreqAmount(1)
    setFreqUnit("days")
    setTargets([])
  }

  const cooldownHours = freqAmount * (UNIT_OPTIONS.find((u) => u.value === freqUnit)?.multiplier ?? 24)

  const handleCreate = async () => {
    const filteredTargets = targets.filter((t) => t.trim())
    await createGoal.mutateAsync({
      id: toSlug(name),
      description: name,
      metrics: { targets: filteredTargets },
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
              <Textarea
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="border-0 shadow-none text-[18px] font-medium text-[#37352f] px-0 min-h-0 py-1 placeholder:text-[#c4c3c0] focus-visible:ring-0 resize-none"
                placeholder="What do you want to achieve?"
                autoFocus
                rows={2}
              />
            </div>

            {/* Properties — Notion inline style */}
            <div className="mt-4 space-y-0 border-t border-[#e8e5df] pt-3">
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
                  onClick={() => setTargets([...targets, ""])}
                  className="text-[12px] text-[#2383e2] hover:underline"
                >
                  + Add
                </button>
              </div>

              {targets.length === 0 ? (
                <button
                  type="button"
                  onClick={() => setTargets([""])}
                  className="w-full text-left text-[12px] text-[#9b9a97] bg-[#f7f6f3] rounded px-3 py-2 hover:bg-[#ebebea] transition-colors"
                >
                  What should the planner aim for? e.g.<br />
                  <span className="text-[#787774]">"Google search ranking top 3"</span>
                </button>
              ) : (
                <div className="space-y-1.5">
                  {targets.map((t, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <Input
                        value={t}
                        onChange={(e) => {
                          const next = [...targets]
                          next[i] = e.target.value
                          setTargets(next)
                        }}
                        className="border-[#e8e5df] text-[13px] text-[#37352f] rounded h-[30px] flex-1"
                        placeholder={i === 0 ? "e.g. Weekly posts 3 or more" : "Add another target..."}
                        autoFocus={!t}
                      />
                      <button
                        type="button"
                        onClick={() => setTargets(targets.filter((_, j) => j !== i))}
                        className="text-[#9b9a97] hover:text-[#eb5757] p-0.5 shrink-0"
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
                disabled={createGoal.isPending || !name.trim()}
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
        <Table className="table-fixed w-full">
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-[40%]">Goal</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-[20%]">Targets</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-[10%]">Frequency</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-[10%]">Last Run</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-[10%]">Active</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide w-[10%]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <TableRow key={i} className="border-[#e8e5df]">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 bg-[#f7f6f3]" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : goals.map((g: any) => {
                  const goalTargets = parseTargets(g.metrics)
                  return (
                    <TableRow key={g.id} className="border-b border-[#e8e5df] hover:bg-[#f7f6f3]">
                      <TableCell className="text-[14px]">
                        <div className="flex items-start gap-2">
                          <Target className="h-4 w-4 text-[#9b9a97] shrink-0 mt-0.5" />
                          <div className="min-w-0">
                            <div className="text-[#37352f] font-medium line-clamp-2">
                              {g.description || g.id}
                            </div>
                            {g.description && g.description !== g.id && (
                              <div className="text-[12px] text-[#9b9a97] font-mono truncate">{g.id}</div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="overflow-hidden">
                        {goalTargets.length > 0 ? (
                          <div className="flex flex-wrap gap-1 min-w-0">
                            {goalTargets.map((t, i) => (
                              <span key={i} className="text-[12px] bg-[#f7f6f3] text-[#787774] border border-[#e8e5df] rounded px-1.5 py-0.5 truncate max-w-full">
                                {t}
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
                        <div className="flex items-center gap-0.5">
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => openEdit(g)}
                            className="h-7 w-7 text-[#9b9a97] hover:text-[#2383e2] hover:bg-[#2383e2]/5"
                            title="Edit"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => triggerGoal.mutate(g.id)}
                            disabled={triggerGoal.isPending || !g.enabled}
                            className="h-7 w-7 text-[#9b9a97] hover:text-[#2383e2] hover:bg-[#2383e2]/5"
                            title="Run now"
                          >
                            <Play className="h-3.5 w-3.5" />
                          </Button>
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
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
            {!isLoading && goals.length === 0 && (
              <TableRow className="border-[#e8e5df]">
                <TableCell colSpan={6} className="text-center text-[14px] text-[#9b9a97] py-8">
                  No goals yet
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Edit Dialog */}
      <Dialog open={!!editGoal} onOpenChange={(v) => { if (!v) setEditGoal(null) }}>
        <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-[420px]">
          <DialogHeader>
            <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Edit Goal</DialogTitle>
          </DialogHeader>

          <div className="mt-3 space-y-1">
            <Textarea
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="border-0 shadow-none text-[18px] font-medium text-[#37352f] px-0 min-h-0 py-1 placeholder:text-[#c4c3c0] focus-visible:ring-0 resize-none"
              placeholder="What do you want to achieve?"
              autoFocus
              rows={2}
            />
          </div>

          <div className="mt-4 space-y-0 border-t border-[#e8e5df] pt-3">
            <PropRow label="Check every">
              <div className="flex items-center gap-0.5">
                <Input
                  type="number"
                  min={1}
                  value={editFreqAmount}
                  onChange={(e) => setEditFreqAmount(Math.max(1, Number(e.target.value) || 1))}
                  className="border-0 shadow-none text-[13px] text-[#37352f] h-[34px] w-[44px] rounded text-center px-0 hover:bg-[#f7f6f3] focus-visible:ring-0"
                />
                <Select value={editFreqUnit} onValueChange={(v) => setEditFreqUnit(v ?? "days")}>
                  <SelectTrigger className="border-0 shadow-none text-[13px] text-[#37352f] h-[34px] w-[76px] rounded hover:bg-[#f7f6f3] focus:ring-0">
                    <SelectValue>{UNIT_OPTIONS.find((u) => u.value === editFreqUnit)?.label ?? "days"}</SelectValue>
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

          <div className="mt-3 border-t border-[#e8e5df] pt-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[13px] text-[#9b9a97]">Targets</span>
              <button
                type="button"
                onClick={() => setEditTargets([...editTargets, ""])}
                className="text-[12px] text-[#2383e2] hover:underline"
              >
                + Add
              </button>
            </div>

            {editTargets.length === 0 ? (
              <button
                type="button"
                onClick={() => setEditTargets([""])}
                className="w-full text-left text-[12px] text-[#9b9a97] bg-[#f7f6f3] rounded px-3 py-2 hover:bg-[#ebebea] transition-colors"
              >
                What should the planner aim for?
              </button>
            ) : (
              <div className="space-y-1.5">
                {editTargets.map((t, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <Input
                      value={t}
                      onChange={(e) => {
                        const next = [...editTargets]
                        next[i] = e.target.value
                        setEditTargets(next)
                      }}
                      className="border-[#e8e5df] text-[13px] text-[#37352f] rounded h-[30px] flex-1"
                      placeholder="Target..."
                    />
                    <button
                      type="button"
                      onClick={() => setEditTargets(editTargets.filter((_, j) => j !== i))}
                      className="text-[#9b9a97] hover:text-[#eb5757] p-0.5 shrink-0"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-[#e8e5df]">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setEditGoal(null)}
              className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3]"
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdate}
              disabled={updateGoal.isPending || !editName.trim()}
              className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3"
            >
              {updateGoal.isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              Save
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
