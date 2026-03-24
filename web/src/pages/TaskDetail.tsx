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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={cn("text-sm text-gray-200", mono && "font-mono")}>{String(value)}</p>
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
        <Skeleton className="h-8 w-48 bg-gray-800" />
        <Skeleton className="h-64 bg-gray-800" />
      </div>
    )
  }

  if (!task) {
    return (
      <div className="text-gray-400">
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
          className="text-gray-400 hover:text-gray-50"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-xl font-semibold text-gray-50">{task.title}</h1>
          <p className="text-xs font-mono text-gray-500 mt-0.5">{task.id}</p>
        </div>
        <StatusBadge status={task.status} className="ml-2" />
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 flex-wrap">
        {canApprove && (
          <Button
            size="sm"
            onClick={() => setApproveOpen(true)}
            className="bg-green-600 hover:bg-green-500 text-white"
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
            className="border-red-500/50 text-red-400 hover:bg-red-500/10"
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
            className="border-gray-700 text-gray-400 hover:bg-gray-800"
          >
            <PenLine className="h-3 w-3 mr-1" />
            Revise
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowTree((v) => !v)}
          className="border-gray-700 text-gray-400 hover:bg-gray-800"
        >
          <Network className="h-3 w-3 mr-1" />
          {showTree ? "Hide Tree" : "Show Tree"}
        </Button>
      </div>

      {/* Main info card */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm text-gray-400">Details</CardTitle>
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
          "border",
          approvalInfo.verdict === "pass" ? "bg-green-500/5 border-green-500/20" :
          approvalInfo.verdict === "fail" ? "bg-red-500/5 border-red-500/20" :
          "bg-gray-800/50 border-gray-700"
        )}>
          <CardContent className="py-4">
            <div className="flex items-start gap-2">
              {approvalInfo.verdict === "pass" ? (
                <CheckCircle2 className="h-4 w-4 text-green-400 mt-0.5 shrink-0" />
              ) : approvalInfo.verdict === "fail" ? (
                <XCircle className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
              ) : (
                <Eye className="h-4 w-4 text-gray-400 mt-0.5 shrink-0" />
              )}
              <div>
                <p className={cn(
                  "text-sm font-medium mb-1",
                  approvalInfo.verdict === "pass" ? "text-green-400" :
                  approvalInfo.verdict === "fail" ? "text-red-400" : "text-gray-300"
                )}>
                  {approvalInfo.verdict === "pass" ? "Review Passed" :
                   approvalInfo.verdict === "fail" ? "Review Failed" : "Review Complete"}
                  {" — Awaiting your approval"}
                </p>
                <p className="text-sm text-gray-400 leading-relaxed">{approvalInfo.reviewSummary}</p>
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
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">Instruction</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-sm text-gray-200 whitespace-pre-wrap font-mono">
              {task.instruction}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Result */}
      {(task.result != null || task.result_json != null) && (
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader
            className="cursor-pointer select-none"
            onClick={() => setResultExpanded((e) => !e)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm text-gray-400">Result</CardTitle>
              {resultExpanded ? (
                <ChevronUp className="h-4 w-4 text-gray-400" />
              ) : (
                <ChevronDown className="h-4 w-4 text-gray-400" />
              )}
            </div>
          </CardHeader>
          {resultExpanded && (
            <CardContent>
              <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-auto max-h-96">
                {typeof (task.result_json ?? task.result) === "string"
                  ? (task.result_json ?? task.result)
                  : JSON.stringify(task.result_json ?? task.result, null, 2)}
              </pre>
            </CardContent>
          )}
        </Card>
      )}

      {/* Children */}
      {children.length > 0 && (
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">
              Child Tasks ({children.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {children.map((child: any) => {
              const review = child.type === "review" ? parseReviewVerdict(child.result_json) : null
              return (
                <div
                  key={child.id}
                  className="flex items-start gap-3 px-3 py-2.5 rounded-lg bg-gray-800/40 hover:bg-gray-800/70 cursor-pointer transition-colors"
                  onClick={() => navigate({ to: "/tasks/$id", params: { id: child.id } })}
                >
                  <StatusBadge status={child.status} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-100">{child.title}</span>
                      <span className="text-xs text-gray-500 font-mono">{child.type}</span>
                      {child.cost_usd > 0 && (
                        <span className="text-xs text-gray-500 font-mono">${Number(child.cost_usd).toFixed(4)}</span>
                      )}
                    </div>
                    {review?.verdict && (
                      <div className="flex items-center gap-1.5 mt-1">
                        {review.verdict === "pass" ? (
                          <CheckCircle2 className="h-3 w-3 text-green-400" />
                        ) : (
                          <XCircle className="h-3 w-3 text-red-400" />
                        )}
                        <span className={cn(
                          "text-xs",
                          review.verdict === "pass" ? "text-green-400" : "text-red-400"
                        )}>
                          {review.verdict === "pass" ? "Passed" : "Failed"}
                        </span>
                        {review.summary && (
                          <span className="text-xs text-gray-500 truncate max-w-md">
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
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">Task Tree</CardTitle>
          </CardHeader>
          <CardContent>
            {treeLoading ? (
              <Skeleton className="h-20 bg-gray-800" />
            ) : treeData ? (
              <TaskTree tree={treeData} />
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* Approve dialog */}
      <Dialog open={approveOpen} onOpenChange={setApproveOpen}>
        <DialogContent className="bg-gray-900 border-gray-800 text-gray-50">
          <DialogHeader>
            <DialogTitle>Approve Task</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="space-y-1">
              <Label className="text-gray-400 text-xs">Note (optional)</Label>
              <Textarea
                value={approveNote}
                onChange={(e) => setApproveNote(e.target.value)}
                className="bg-gray-800 border-gray-700 text-gray-50"
                placeholder="Instructions for the agent..."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setApproveOpen(false)} className="text-gray-400">
                Cancel
              </Button>
              <Button
                onClick={() => {
                  approve.mutate({ id, note: approveNote || undefined })
                  setApproveOpen(false)
                  setApproveNote("")
                }}
                disabled={approve.isPending}
                className="bg-green-600 hover:bg-green-500 text-white"
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
        <DialogContent className="bg-gray-900 border-gray-800 text-gray-50">
          <DialogHeader>
            <DialogTitle>Reject Task</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="space-y-1">
              <Label className="text-gray-400 text-xs">Note (optional)</Label>
              <Textarea
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                className="bg-gray-800 border-gray-700 text-gray-50"
                placeholder="Reason for rejection..."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setRejectOpen(false)}
                className="text-gray-400"
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
                className="bg-red-600 hover:bg-red-500 text-white"
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
        <DialogContent className="bg-gray-900 border-gray-800 text-gray-50">
          <DialogHeader>
            <DialogTitle>Request Revision</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="space-y-1">
              <Label className="text-gray-400 text-xs">Revision Note *</Label>
              <Textarea
                value={reviseNote}
                onChange={(e) => setReviseNote(e.target.value)}
                className="bg-gray-800 border-gray-700 text-gray-50"
                placeholder="Describe the changes needed..."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setReviseOpen(false)}
                className="text-gray-400"
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
                className="bg-indigo-600 hover:bg-indigo-500 text-white"
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
