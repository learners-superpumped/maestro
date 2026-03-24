import { useState } from "react"
import { useNavigate } from "@tanstack/react-router"
import { useRootTasks, useApproveTask, useRejectTask } from "@/hooks/queries/use-tasks"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Check, X, ExternalLink, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export function ActionRequired() {
  const { data } = useRootTasks()
  const approve = useApproveTask()
  const reject = useRejectTask()
  const navigate = useNavigate()
  const [dialogTask, setDialogTask] = useState<any>(null)
  const [dialogType, setDialogType] = useState<"approve" | "reject" | null>(null)
  const [note, setNote] = useState("")

  // Filter for actionable tasks
  const tasks = (data?.tasks ?? []).filter((t: any) =>
    ["pending", "paused", "failed"].includes(t.status)
  )

  if (tasks.length === 0) return null  // Auto-hide

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-amber-400 flex items-center gap-2">
        Action Required ({tasks.length})
      </h2>
      <div className="space-y-2">
        {tasks.map((task: any) => (
          <div
            key={task.id}
            className={cn(
              "flex items-center justify-between px-4 py-3 rounded-lg border",
              task.status === "failed"
                ? "bg-red-500/10 border-red-500/30"
                : "bg-amber-500/10 border-amber-500/30"
            )}
          >
            <div className="flex items-center gap-3 min-w-0">
              <StatusBadge status={task.status} />
              <span className="text-sm text-gray-50 truncate">{task.title}</span>
              <span className="text-xs text-gray-500">{task.workspace}</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {task.status !== "failed" && (
                <>
                  <Button size="sm" onClick={() => { setDialogTask(task); setDialogType("approve"); setNote("") }}
                    className="bg-green-600 hover:bg-green-500 text-white h-7 text-xs">
                    <Check className="h-3 w-3 mr-1" /> Approve
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => { setDialogTask(task); setDialogType("reject"); setNote("") }}
                    className="border-red-500/50 text-red-400 hover:bg-red-500/10 h-7 text-xs">
                    <X className="h-3 w-3 mr-1" /> Reject
                  </Button>
                </>
              )}
              {task.status === "failed" && (
                <Button size="sm" variant="outline" onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
                  className="border-gray-700 text-gray-400 h-7 text-xs">
                  <ExternalLink className="h-3 w-3 mr-1" /> View
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Approve/Reject dialog */}
      <Dialog open={!!dialogTask} onOpenChange={(open) => { if (!open) { setDialogTask(null); setDialogType(null) } }}>
        <DialogContent className="bg-gray-900 border-gray-800 text-gray-50">
          <DialogHeader>
            <DialogTitle>{dialogType === "approve" ? "Approve" : "Reject"} Task</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="space-y-1">
              <Label className="text-gray-400 text-xs">Note (optional)</Label>
              <Textarea value={note} onChange={(e) => setNote(e.target.value)}
                className="bg-gray-800 border-gray-700 text-gray-50"
                placeholder={dialogType === "approve" ? "Instructions..." : "Reason..."} />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDialogTask(null)} className="text-gray-400">Cancel</Button>
              <Button onClick={() => {
                if (dialogType === "approve") approve.mutate({ id: dialogTask.id, note: note || undefined })
                else reject.mutate({ id: dialogTask.id, note: note || undefined })
                setDialogTask(null)
              }}
              disabled={approve.isPending || reject.isPending}
              className={dialogType === "approve" ? "bg-green-600 hover:bg-green-500 text-white" : "bg-red-600 hover:bg-red-500 text-white"}>
                {(approve.isPending || reject.isPending) && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                {dialogType === "approve" ? "Approve" : "Reject"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
