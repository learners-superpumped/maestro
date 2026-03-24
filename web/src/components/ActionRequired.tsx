import { useState } from "react"
import { useNavigate } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import { useRootTasks, useApproveTask, useRejectTask, useReviseTask, useCreateTask } from "@/hooks/queries/use-tasks"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Check, X, PenLine, Play, RefreshCw, ExternalLink, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronRight } from "lucide-react"
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
  const retryTask = useCreateTask()
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
        "bg-white border rounded px-4 py-3 space-y-2",
        task.status === "failed"
          ? "border-[#e8e5df] border-l-2 border-l-[#eb5757]"
          : isPassed
          ? "border-[#e8e5df] border-l-2 border-l-[#4dab9a]"
          : "border-[#e8e5df]"
      )}>
        {/* Row 1: Status + Title + Workspace + Actions */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <StatusBadge status={task.status} />
            <span
              className="text-[14px] text-[#37352f] truncate cursor-pointer hover:underline"
              onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
            >
              {task.title}
            </span>
            <span className="text-[12px] text-[#9b9a97] shrink-0">{task.workspace}</span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {task.status === "pending" && (
              <>
                <Button size="sm" onClick={() => { setDialogType("approve"); setNote("") }}
                  className="bg-[#2383e2] hover:bg-[#1a73cc] text-white h-[28px] text-[12px] rounded px-2.5">
                  <Play className="h-3 w-3 mr-1" /> Start
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setDialogType("reject"); setNote("") }}
                  className="border border-[#e8e5df] text-[#787774] hover:bg-[#f7f6f3] h-[28px] text-[12px] rounded px-2.5">
                  <X className="h-3 w-3 mr-1" /> Cancel
                </Button>
              </>
            )}
            {task.status === "paused" && (
              <>
                <Button size="sm" onClick={() => { setDialogType("approve"); setNote("") }}
                  className="bg-[#4dab9a] hover:bg-[#3d9b8b] text-white h-[28px] text-[12px] rounded px-2.5">
                  <Check className="h-3 w-3 mr-1" /> Approve
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setDialogType("revise"); setNote("") }}
                  className="border border-[#e8e5df] text-[#787774] hover:bg-[#f7f6f3] h-[28px] text-[12px] rounded px-2.5">
                  <PenLine className="h-3 w-3 mr-1" /> Revise
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setDialogType("reject"); setNote("") }}
                  className="border border-[#e8e5df] text-[#eb5757] hover:bg-red-50 h-[28px] text-[12px] rounded px-2.5">
                  <X className="h-3 w-3 mr-1" /> Reject
                </Button>
              </>
            )}
            {task.status === "failed" && (
              <>
                <Button size="sm" onClick={async () => {
                  await retryTask.mutateAsync({
                    workspace: task.workspace, type: task.type,
                    title: task.title, instruction: task.instruction,
                    priority: task.priority, approval_level: task.approval_level,
                  })
                }}
                  disabled={retryTask.isPending}
                  className="bg-[#2383e2] hover:bg-[#1a73cc] text-white h-[28px] text-[12px] rounded px-2.5">
                  {retryTask.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <RefreshCw className="h-3 w-3 mr-1" />} Retry
                </Button>
                <Button size="sm" variant="outline" onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
                  className="border border-[#e8e5df] text-[#787774] h-[28px] text-[12px] rounded px-2.5">
                  <ExternalLink className="h-3 w-3 mr-1" /> View
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Row 2: Review verdict + summary */}
        {review.summary && (
          <div className="flex items-start gap-2 ml-1">
            {isPassed && <CheckCircle2 className="h-3.5 w-3.5 text-[#4dab9a] mt-0.5 shrink-0" />}
            {isFailed && <XCircle className="h-3.5 w-3.5 text-[#eb5757] mt-0.5 shrink-0" />}
            {!isPassed && !isFailed && <CheckCircle2 className="h-3.5 w-3.5 text-[#9b9a97] mt-0.5 shrink-0" />}
            <div className="min-w-0">
              <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1 text-[12px] text-[#9b9a97] hover:text-[#37352f]"
              >
                <span className={cn(
                  "font-medium",
                  isPassed && "text-[#4dab9a]",
                  isFailed && "text-[#eb5757]",
                )}>
                  {isPassed ? "Review passed" : isFailed ? "Review failed" : "Review complete"}
                </span>
                <span className="text-[#9b9a97]">—</span>
                <span className="truncate max-w-md">{review.summary}</span>
                {expanded ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
              </button>
              {expanded && (
                <p className="text-[12px] text-[#9b9a97] mt-1.5 leading-relaxed">
                  {review.summary}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Row 3: Failed task error */}
        {task.status === "failed" && task.error && (
          <p className="text-[12px] text-[#eb5757] ml-1">{task.error}</p>
        )}
      </div>

      {/* Action dialog */}
      <Dialog open={!!dialogType} onOpenChange={(open) => { if (!open) setDialogType(null) }}>
        <DialogContent className="bg-white border border-[#e8e5df] max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[16px] font-semibold text-[#37352f]">
              {dialogType === "approve" ? "Approve" : dialogType === "revise" ? "Request Revision" : "Reject"} — {task.title}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            {review.summary && (
              <div className="text-[12px] text-[#787774] bg-[#f7f6f3] rounded p-3 leading-relaxed">
                <span className="font-medium text-[#37352f]">Review: </span>
                {review.summary}
              </div>
            )}
            <div className="space-y-1">
              <Label className="text-[12px] text-[#9b9a97]">
                {dialogType === "revise" ? "Revision instructions *" : "Note (optional)"}
              </Label>
              <Textarea value={note} onChange={(e) => setNote(e.target.value)}
                className="bg-white border-[#e8e5df] text-[#37352f]"
                placeholder={
                  dialogType === "approve" ? "Any instructions for the agent..."
                    : dialogType === "revise" ? "What should be changed..."
                    : "Reason for rejection..."
                } />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDialogType(null)} className="text-[#787774] hover:bg-[#f7f6f3]">Cancel</Button>
              <Button
                onClick={handleAction}
                disabled={approve.isPending || reject.isPending || revise.isPending || (dialogType === "revise" && !note.trim())}
                className={cn(
                  "text-white",
                  dialogType === "approve" && "bg-[#4dab9a] hover:bg-[#3d9b8b]",
                  dialogType === "revise" && "bg-[#2383e2] hover:bg-[#1a73cc]",
                  dialogType === "reject" && "bg-[#eb5757] hover:bg-red-600",
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
      <h2 className="text-[14px] font-semibold text-[#37352f]">
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
