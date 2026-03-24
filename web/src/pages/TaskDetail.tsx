import { useState } from "react"
import { useParams, useNavigate } from "@tanstack/react-router"
import {
  useTask,
  useTaskChildren,
  useApproveTask,
  useRejectTask,
  useReviseTask,
  useTaskTree,
} from "@/hooks/queries/use-tasks"
import { TaskTree } from "@/components/TaskTree"
import { StatusBadge } from "@/components/StatusBadge"
import { ActivityTimeline } from "@/components/ActivityTimeline"
import { AgentLogPanel } from "@/components/AgentLogPanel"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Loader2,
  Check,
  X,
  PenLine,
  Network,
} from "lucide-react"
import Markdown from "react-markdown"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import { cn } from "@/lib/utils"
import { CheckCircle2, XCircle, Eye } from "lucide-react"

function parseReviewVerdict(resultJson: any): { verdict: string | null; summary: string | null } {
  const raw = typeof resultJson === "string" ? resultJson : JSON.stringify(resultJson ?? "")
  const match = raw.match(/"verdict"\s*:\s*"(\w+)"/)
  const summaryMatch = raw.match(/"summary"\s*:\s*"((?:[^"\\]|\\.)*)"/)
  return {
    verdict: match ? match[1] : null,
    summary: summaryMatch ? summaryMatch[1].replace(/\\n/g, " ").replace(/\\\"/g, '"') : null,
  }
}

function parseApprovalDraft(draftJson: any): { verdict: string | null; reviewSummary: string | null } {
  if (!draftJson) return { verdict: null, reviewSummary: null }
  try {
    const draft = typeof draftJson === "string" ? JSON.parse(draftJson) : draftJson
    const reviewSummary = draft.review_summary || null
    let verdict: string | null = null
    const resultStr = draft.result || ""
    const jsonMatch = resultStr.match(/```json\s*\n?([\s\S]*?)\n?```/)
    if (jsonMatch) {
      try { verdict = JSON.parse(jsonMatch[1]).verdict || null } catch {}
    }
    return { verdict, reviewSummary }
  } catch { return { verdict: null, reviewSummary: null } }
}

function Field({ label, value, mono }: { label: string; value?: any; mono?: boolean }) {
  if (value == null || value === "") return null
  return (
    <div>
      <p className="text-[12px] text-[#9b9a97] mb-0.5">{label}</p>
      <p className={cn("text-[14px] text-[#37352f]", mono && "text-[13px] font-mono text-[#787774]")}>{String(value)}</p>
    </div>
  )
}

export function TaskDetail() {
  const { id } = useParams({ from: "/tasks/$id" })
  const navigate = useNavigate()

  const { data: task, isLoading } = useTask(id)
  const { data: childrenData } = useTaskChildren(id)

  const approve = useApproveTask()
  const reject = useRejectTask()
  const revise = useReviseTask()

  const [approveOpen, setApproveOpen] = useState(false)
  const [approveNote, setApproveNote] = useState("")
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectNote, setRejectNote] = useState("")
  const [reviseOpen, setReviseOpen] = useState(false)
  const [reviseNote, setReviseNote] = useState("")
  const [resultExpanded, setResultExpanded] = useState(false)
  const [showTree, setShowTree] = useState(false)

  const { data: treeData, isLoading: treeLoading } = useTaskTree(showTree ? id : "")

  const children: any[] = childrenData?.children ?? []

  // Fetch approval draft for paused tasks
  const { data: approval } = useQuery({
    queryKey: ["approval", id],
    queryFn: () => api.approvals.get(id),
    enabled: task?.status === "paused",
    retry: false,
  })
  const approvalInfo = parseApprovalDraft(approval?.draft_json)

  const canApprove = task?.status === "pending" || task?.status === "paused"
  const canReject = task?.status === "pending" || task?.status === "paused"
  const canRevise = task?.status === "paused"

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48 bg-[#f7f6f3]" />
        <Skeleton className="h-64 bg-[#f7f6f3]" />
      </div>
    )
  }

  if (!task) {
    return (
      <div className="text-[14px] text-[#9b9a97]">
        Task not found.
      </div>
    )
  }

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate({ to: "/tasks" })}
          className="text-[#9b9a97] hover:text-[#37352f] hover:bg-[#f7f6f3]"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-[20px] font-semibold text-[#37352f]">{task.title}</h1>
          <p className="text-[12px] font-mono text-[#9b9a97] mt-0.5">{task.id}</p>
        </div>
        <StatusBadge status={task.status} className="ml-2" />
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 flex-wrap">
        {canApprove && (
          <Button
            size="sm"
            onClick={() => setApproveOpen(true)}
            className="h-[28px] text-[13px] rounded bg-[#4dab9a] hover:bg-[#3d9b8b] text-white px-3"
          >
            <Check className="h-3 w-3 mr-1" />
            Approve
          </Button>
        )}
        {canReject && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setRejectOpen(true)}
            className="h-[28px] text-[13px] rounded border border-[#e8e5df] text-[#eb5757] hover:bg-red-50 px-3"
          >
            <X className="h-3 w-3 mr-1" />
            Reject
          </Button>
        )}
        {canRevise && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setReviseOpen(true)}
            className="h-[28px] text-[13px] rounded border border-[#e8e5df] text-[#787774] hover:bg-[#f7f6f3] px-3"
          >
            <PenLine className="h-3 w-3 mr-1" />
            Revise
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowTree((v) => !v)}
          className="h-[28px] text-[13px] rounded border border-[#e8e5df] text-[#787774] hover:bg-[#f7f6f3] px-3"
        >
          <Network className="h-3 w-3 mr-1" />
          {showTree ? "Hide Tree" : "Show Tree"}
        </Button>
      </div>

      {/* Main info card */}
      <Card className="bg-white border border-[#e8e5df] rounded">
        <CardHeader>
          <CardTitle className="text-[12px] text-[#9b9a97]">Details</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <Field label="Workspace" value={task.workspace} />
          <Field label="Type" value={task.type} />
          <Field label="Status" value={task.status} />
          <Field label="Priority" value={task.priority} />
          <Field label="Approval Level" value={task.approval_level} />
          <Field label="Cost" value={task.cost_usd != null ? `$${Number(task.cost_usd).toFixed(6)}` : undefined} />
          <Field label="Created At" value={task.created_at ? new Date(task.created_at).toLocaleString() : undefined} />
          <Field label="Updated At" value={task.updated_at ? new Date(task.updated_at).toLocaleString() : undefined} />
          <Field label="Created By" value={task.created_by} mono />
          <Field label="Claimed By" value={task.claimed_by} mono />
          <Field label="Attempt" value={task.max_retries ? `${task.attempt ?? 0}/${task.max_retries}` : undefined} />
          <Field label="Reviews" value={task.review_count || undefined} />
        </CardContent>
      </Card>

      {/* Review Summary (for paused tasks with approval) */}
      {approvalInfo.reviewSummary && (
        <Card className={cn(
          "border rounded",
          approvalInfo.verdict === "pass" ? "bg-[#4dab9a]/5 border-[#4dab9a]/20" :
          approvalInfo.verdict === "fail" ? "bg-[#eb5757]/5 border-[#eb5757]/20" :
          "bg-[#f7f6f3] border-[#e8e5df]"
        )}>
          <CardContent className="py-4">
            <div className="flex items-start gap-2">
              {approvalInfo.verdict === "pass" ? (
                <CheckCircle2 className="h-4 w-4 text-[#4dab9a] mt-0.5 shrink-0" />
              ) : approvalInfo.verdict === "fail" ? (
                <XCircle className="h-4 w-4 text-[#eb5757] mt-0.5 shrink-0" />
              ) : (
                <Eye className="h-4 w-4 text-[#9b9a97] mt-0.5 shrink-0" />
              )}
              <div>
                <p className={cn(
                  "text-[14px] font-medium mb-1",
                  approvalInfo.verdict === "pass" ? "text-[#4dab9a]" :
                  approvalInfo.verdict === "fail" ? "text-[#eb5757]" : "text-[#787774]"
                )}>
                  {approvalInfo.verdict === "pass" ? "Review Passed" :
                   approvalInfo.verdict === "fail" ? "Review Failed" : "Review Complete"}
                  {" — Awaiting your approval"}
                </p>
                <p className="text-[14px] text-[#787774] leading-relaxed">{approvalInfo.reviewSummary}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Agent Log Panel */}
      {(task.status === "running" || task.status === "completed" || task.status === "failed" || task.status === "paused") && (
        <AgentLogPanel taskId={id} taskStatus={task.status} />
      )}

      {/* Activity Timeline */}
      <ActivityTimeline taskId={id} />

      {/* Instruction */}
      {task.instruction && (
        <Card className="bg-white border border-[#e8e5df] rounded">
          <CardHeader>
            <CardTitle className="text-[12px] text-[#9b9a97]">Instruction</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-[14px] text-[#37352f] whitespace-pre-wrap font-mono">
              {task.instruction}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Result */}
      {(task.result != null || task.result_json != null) && (
        <Card className="bg-white border border-[#e8e5df] rounded">
          <CardHeader
            className="cursor-pointer select-none"
            onClick={() => setResultExpanded((e) => !e)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-[12px] text-[#9b9a97]">Result</CardTitle>
              {resultExpanded ? (
                <ChevronUp className="h-4 w-4 text-[#9b9a97]" />
              ) : (
                <ChevronDown className="h-4 w-4 text-[#9b9a97]" />
              )}
            </div>
          </CardHeader>
          {resultExpanded && (
            <CardContent>
              <div className="prose max-w-none overflow-auto max-h-[600px]">
                <Markdown>
                  {typeof (task.result_json ?? task.result) === "string"
                    ? (task.result_json ?? task.result)
                    : JSON.stringify(task.result_json ?? task.result, null, 2)}
                </Markdown>
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Children */}
      {children.length > 0 && (
        <Card className="bg-white border border-[#e8e5df] rounded">
          <CardHeader>
            <CardTitle className="text-[12px] text-[#9b9a97]">
              Child Tasks ({children.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {children.map((child: any) => {
              const review = child.type === "review" ? parseReviewVerdict(child.result_json) : null
              return (
                <div
                  key={child.id}
                  className="flex items-start gap-3 px-3 py-2.5 rounded bg-[#f7f6f3] hover:bg-[#ebebea] cursor-pointer transition-colors"
                  onClick={() => navigate({ to: "/tasks/$id", params: { id: child.id } })}
                >
                  <StatusBadge status={child.status} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] text-[#37352f]">{child.title}</span>
                      <span className="text-[12px] text-[#9b9a97] font-mono">{child.type}</span>
                      {child.cost_usd > 0 && (
                        <span className="text-[12px] text-[#9b9a97] font-mono">${Number(child.cost_usd).toFixed(4)}</span>
                      )}
                    </div>
                    {review?.verdict && (
                      <div className="flex items-center gap-1.5 mt-1">
                        {review.verdict === "pass" ? (
                          <CheckCircle2 className="h-3 w-3 text-[#4dab9a]" />
                        ) : (
                          <XCircle className="h-3 w-3 text-[#eb5757]" />
                        )}
                        <span className={cn(
                          "text-[12px]",
                          review.verdict === "pass" ? "text-[#4dab9a]" : "text-[#eb5757]"
                        )}>
                          {review.verdict === "pass" ? "Passed" : "Failed"}
                        </span>
                        {review.summary && (
                          <span className="text-[12px] text-[#9b9a97] truncate max-w-md">
                            — {review.summary}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* Task Tree */}
      {showTree && (
        <Card className="bg-white border border-[#e8e5df] rounded">
          <CardHeader>
            <CardTitle className="text-[12px] text-[#9b9a97]">Task Tree</CardTitle>
          </CardHeader>
          <CardContent>
            {treeLoading ? (
              <Skeleton className="h-20 bg-[#f7f6f3]" />
            ) : treeData ? (
              <TaskTree tree={treeData} />
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* Approve dialog */}
      <Dialog open={approveOpen} onOpenChange={setApproveOpen}>
        <DialogContent className="bg-white border-[#e8e5df]">
          <DialogHeader>
            <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Approve Task</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="space-y-1">
              <Label className="text-[12px] text-[#9b9a97]">Note (optional)</Label>
              <Textarea
                value={approveNote}
                onChange={(e) => setApproveNote(e.target.value)}
                className="bg-white border-[#e8e5df] text-[#37352f]"
                placeholder="Instructions for the agent..."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setApproveOpen(false)} className="text-[#787774] hover:bg-[#f7f6f3]">
                Cancel
              </Button>
              <Button
                onClick={() => {
                  approve.mutate({ id, note: approveNote || undefined })
                  setApproveOpen(false)
                  setApproveNote("")
                }}
                disabled={approve.isPending}
                className="bg-[#4dab9a] hover:bg-[#3d9b8b] text-white"
              >
                {approve.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                Approve
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reject dialog */}
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent className="bg-white border-[#e8e5df]">
          <DialogHeader>
            <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Reject Task</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="space-y-1">
              <Label className="text-[12px] text-[#9b9a97]">Note (optional)</Label>
              <Textarea
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                className="bg-white border-[#e8e5df] text-[#37352f]"
                placeholder="Reason for rejection..."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setRejectOpen(false)}
                className="text-[#787774] hover:bg-[#f7f6f3]"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  reject.mutate({ id, note: rejectNote || undefined })
                  setRejectOpen(false)
                  setRejectNote("")
                }}
                disabled={reject.isPending}
                className="bg-[#eb5757] hover:bg-red-500 text-white"
              >
                {reject.isPending && (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                )}
                Reject
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Revise dialog */}
      <Dialog open={reviseOpen} onOpenChange={setReviseOpen}>
        <DialogContent className="bg-white border-[#e8e5df]">
          <DialogHeader>
            <DialogTitle className="text-[16px] font-semibold text-[#37352f]">Request Revision</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="space-y-1">
              <Label className="text-[12px] text-[#9b9a97]">Revision Note *</Label>
              <Textarea
                value={reviseNote}
                onChange={(e) => setReviseNote(e.target.value)}
                className="bg-white border-[#e8e5df] text-[#37352f]"
                placeholder="Describe the changes needed..."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setReviseOpen(false)}
                className="text-[#787774] hover:bg-[#f7f6f3]"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  if (!reviseNote.trim()) return
                  revise.mutate({ id, note: reviseNote })
                  setReviseOpen(false)
                  setReviseNote("")
                }}
                disabled={revise.isPending || !reviseNote.trim()}
                className="bg-[#2383e2] hover:bg-blue-500 text-white"
              >
                {revise.isPending && (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                )}
                Send
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
