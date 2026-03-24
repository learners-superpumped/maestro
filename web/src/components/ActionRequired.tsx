import { useState } from "react"
import { useNavigate } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import { useRootTasks, useApproveTask, useRejectTask, useReviseTask } from "@/hooks/queries/use-tasks"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Check, X, PenLine, ExternalLink, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/api/client"

function parseReviewFromDraft(draftJson: any): { verdict: string | null; summary: string | null } {
  if (!draftJson) return { verdict: null, summary: null }
  try {
    const draft = typeof draftJson === "string" ? JSON.parse(draftJson) : draftJson
    // review_summary is the top-level field
    const summary = draft.review_summary || null
    // verdict is inside the result field (which contains markdown with JSON)
    let verdict: string | null = null
    const resultStr = draft.result || ""
    const jsonMatch = resultStr.match(/```json\s*\n?([\s\S]*?)\n?```/)
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[1])
        verdict = parsed.verdict || null
      } catch { /* ignore */ }
    }
    return { verdict, summary }
  } catch {
    return { verdict: null, summary: null }
  }
}

function ApprovalCard({ task }: { task: any }) {
  const navigate = useNavigate()
  const approve = useApproveTask()
  const reject = useRejectTask()
  const revise = useReviseTask()
  const [expanded, setExpanded] = useState(false)
  const [dialogType, setDialogType] = useState<"approve" | "reject" | "revise" | null>(null)
  const [note, setNote] = useState("")

  // Fetch approval draft for this task
  const { data: approval } = useQuery({
    queryKey: ["approval", task.id],
    queryFn: () => api.approvals.get(task.id),
    enabled: task.status === "paused",
    retry: false,
  })

  const review = parseReviewFromDraft(approval?.draft_json)
  const isPassed = review.verdict === "pass"
  const isFailed = review.verdict === "fail"

  const handleAction = () => {
    if (dialogType === "approve") approve.mutate({ id: task.id, note: note || undefined })
    else if (dialogType === "reject") reject.mutate({ id: task.id, note: note || undefined })
    else if (dialogType === "revise") revise.mutate({ id: task.id, note })
    setDialogType(null)
    setNote("")
  }

  return (
    <>
      <div className={cn(
        "rounded-lg border px-4 py-3 space-y-2",
        task.status === "failed"
          ? "bg-red-500/5 border-red-500/20"
          : "bg-gray-800/50 border-gray-700"
      )}>
        {/* Row 1: Status + Title + Workspace + Actions */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <StatusBadge status={task.status} />
            <span
              className="text-sm text-gray-100 truncate cursor-pointer hover:underline"
              onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
            >
              {task.title}
            </span>
            <span className="text-xs text-gray-500 shrink-0">{task.workspace}</span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {task.status !== "failed" && (
              <>
                <Button size="sm" onClick={() => { setDialogType("approve"); setNote("") }}
                  className="bg-green-600 hover:bg-green-500 text-white h-7 text-xs px-2.5">
                  <Check className="h-3 w-3 mr-1" /> Approve
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setDialogType("revise"); setNote("") }}
                  className="border-gray-600 text-gray-300 hover:bg-gray-700 h-7 text-xs px-2.5">
                  <PenLine className="h-3 w-3 mr-1" /> Revise
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setDialogType("reject"); setNote("") }}
                  className="border-red-500/40 text-red-400 hover:bg-red-500/10 h-7 text-xs px-2.5">
                  <X className="h-3 w-3 mr-1" /> Reject
                </Button>
              </>
            )}
            {task.status === "failed" && (
              <Button size="sm" variant="outline" onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
                className="border-gray-600 text-gray-300 h-7 text-xs px-2.5">
                <ExternalLink className="h-3 w-3 mr-1" /> View
              </Button>
            )}
          </div>
        </div>

        {/* Row 2: Review verdict + summary */}
        {review.summary && (
          <div className="flex items-start gap-2 ml-1">
            {isPassed && <CheckCircle2 className="h-3.5 w-3.5 text-green-400 mt-0.5 shrink-0" />}
            {isFailed && <XCircle className="h-3.5 w-3.5 text-red-400 mt-0.5 shrink-0" />}
            {!isPassed && !isFailed && <CheckCircle2 className="h-3.5 w-3.5 text-gray-500 mt-0.5 shrink-0" />}
            <div className="min-w-0">
              <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200"
              >
                <span className={cn(
                  "font-medium",
                  isPassed && "text-green-400",
                  isFailed && "text-red-400",
                )}>
                  {isPassed ? "Review passed" : isFailed ? "Review failed" : "Review complete"}
                </span>
                <span className="text-gray-500">—</span>
                <span className="truncate max-w-md">{review.summary}</span>
                {expanded ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
              </button>
              {expanded && (
                <p className="text-xs text-gray-400 mt-1.5 leading-relaxed">
                  {review.summary}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Row 3: Failed task error */}
        {task.status === "failed" && task.error && (
          <p className="text-xs text-red-400 ml-1">{task.error}</p>
        )}
      </div>

      {/* Action dialog */}
      <Dialog open={!!dialogType} onOpenChange={(open) => { if (!open) setDialogType(null) }}>
        <DialogContent className="bg-gray-900 border-gray-800 text-gray-50 max-w-md">
          <DialogHeader>
            <DialogTitle>
              {dialogType === "approve" ? "Approve" : dialogType === "revise" ? "Request Revision" : "Reject"} — {task.title}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            {review.summary && (
              <div className="text-xs text-gray-400 bg-gray-800 rounded p-3 leading-relaxed">
                <span className="font-medium text-gray-300">Review: </span>
                {review.summary}
              </div>
            )}
            <div className="space-y-1">
              <Label className="text-gray-400 text-xs">
                {dialogType === "revise" ? "Revision instructions *" : "Note (optional)"}
              </Label>
              <Textarea value={note} onChange={(e) => setNote(e.target.value)}
                className="bg-gray-800 border-gray-700 text-gray-50"
                placeholder={
                  dialogType === "approve" ? "Any instructions for the agent..."
                    : dialogType === "revise" ? "What should be changed..."
                    : "Reason for rejection..."
                } />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDialogType(null)} className="text-gray-400">Cancel</Button>
              <Button
                onClick={handleAction}
                disabled={approve.isPending || reject.isPending || revise.isPending || (dialogType === "revise" && !note.trim())}
                className={cn(
                  dialogType === "approve" && "bg-green-600 hover:bg-green-500 text-white",
                  dialogType === "revise" && "bg-indigo-600 hover:bg-indigo-500 text-white",
                  dialogType === "reject" && "bg-red-600 hover:bg-red-500 text-white",
                )}>
                {(approve.isPending || reject.isPending || revise.isPending) && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                {dialogType === "approve" ? "Approve" : dialogType === "revise" ? "Send Revision" : "Reject"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export function ActionRequired() {
  const { data } = useRootTasks()

  const tasks = (data?.tasks ?? []).filter((t: any) =>
    ["pending", "paused", "failed"].includes(t.status)
  )

  if (tasks.length === 0) return null

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-amber-400">
        Action Required ({tasks.length})
      </h2>
      <div className="space-y-2">
        {tasks.map((task: any) => (
          <ApprovalCard key={task.id} task={task} />
        ))}
      </div>
    </div>
  )
}
