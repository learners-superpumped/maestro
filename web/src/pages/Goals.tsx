import { useState } from "react"
import { Plus, Trash2, Loader2, Target } from "lucide-react"
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
import { Textarea } from "@/components/ui/textarea"

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

export function Goals() {
  const [open, setOpen] = useState(false)
  const [formId, setFormId] = useState("")
  const [formWorkspace, setFormWorkspace] = useState("")
  const [formDescription, setFormDescription] = useState("")
  const [formMetrics, setFormMetrics] = useState("{}")
  const [formCooldown, setFormCooldown] = useState(24)

  const { data, isLoading } = useGoals()
  const createGoal = useCreateGoal()
  const deleteGoal = useDeleteGoal()
  const toggleGoal = useToggleGoal()

  const { data: wsData } = useWorkspaces()
  const workspaces: any[] = wsData?.workspaces ?? []

  const goals: any[] = data?.goals ?? []

  const handleCreate = async () => {
    let metrics = {}
    try {
      metrics = JSON.parse(formMetrics)
    } catch { /* use empty */ }
    await createGoal.mutateAsync({
      id: formId,
      workspace: formWorkspace,
      description: formDescription,
      metrics,
      cooldown_hours: formCooldown,
    })
    setFormId("")
    setFormWorkspace("")
    setFormDescription("")
    setFormMetrics("{}")
    setFormCooldown(24)
    setOpen(false)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-[#37352f]">Goals</h1>
          <p className="text-[14px] text-[#787774] mt-1">
            {data?.count != null ? `${data.count} goals` : ""}
          </p>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button className="h-[28px] text-[13px] bg-[#2383e2] hover:bg-[#1a73cc] text-white rounded px-3">
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Goal
              </Button>
            }
          />
          <DialogContent className="bg-white border border-[#e8e5df] text-[#37352f] max-w-lg">
            <DialogHeader>
              <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Add Goal</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">ID *</Label>
                  <Input
                    value={formId}
                    onChange={(e) => setFormId(e.target.value)}
                    className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                    placeholder="threads-presence"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Workspace *</Label>
                  <Select value={formWorkspace} onValueChange={setFormWorkspace}>
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
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-[12px] text-[#9b9a97]">Description</Label>
                <Input
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                  placeholder="Threads brand presence"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Metrics (JSON)</Label>
                  <Textarea
                    value={formMetrics}
                    onChange={(e) => setFormMetrics(e.target.value)}
                    className="bg-white border-[#e8e5df] text-[#37352f] font-mono text-[13px] rounded h-[60px]"
                    placeholder='{"post_frequency": "3/week"}'
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[12px] text-[#9b9a97]">Cooldown (hours)</Label>
                  <Input
                    type="number"
                    value={formCooldown}
                    onChange={(e) => setFormCooldown(Number(e.target.value))}
                    className="bg-white border-[#e8e5df] text-[#37352f] text-[14px] rounded"
                  />
                </div>
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
                  onClick={handleCreate}
                  disabled={createGoal.isPending || !formId || !formWorkspace}
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

      <div className="rounded border border-[#e8e5df] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">ID</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Workspace</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Cooldown</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Last Evaluated</TableHead>
              <TableHead className="text-[12px] font-medium text-[#9b9a97] uppercase tracking-wide">Gap</TableHead>
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
              : goals.map((g: any) => (
                  <TableRow key={g.id} className="border-b border-[#e8e5df] hover:bg-[#f7f6f3]">
                    <TableCell className="text-[#37352f] text-[14px] font-medium">
                      <div className="flex items-center gap-2">
                        <Target className="h-4 w-4 text-[#9b9a97]" />
                        {g.id}
                      </div>
                    </TableCell>
                    <TableCell className="text-[14px] text-[#787774]">{g.workspace}</TableCell>
                    <TableCell className="text-[14px] text-[#787774]">{g.cooldown_hours}h</TableCell>
                    <TableCell className="text-[12px] text-[#9b9a97]">
                      {formatRelativeTime(g.last_evaluated_at)}
                    </TableCell>
                    <TableCell className="text-[12px] text-[#9b9a97] max-w-xs truncate">
                      {g.current_gap || "\u2014"}
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
                ))}
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
