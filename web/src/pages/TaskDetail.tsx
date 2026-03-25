import { useState } from "react"
import { useParams, useNavigate } from "@tanstack/react-router"
import {
  useTask,
  useTaskChildren,
  useApproveTask,
  useRejectTask,
  useReviseTask,
  useCreateTask,
} from "@/hooks/queries/use-tasks"
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
  ChevronRight,
  Loader2,
  Check,
  X,
  PenLine,
  AlertTriangle,
  Play,
  RefreshCw,
} from "lucide-react"
import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import { cn } from "@/lib/utils"
import { TaskTypeBadge, getTaskTypeLabel } from "@/components/TaskTypeBadge"
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

function CollapsibleSection({ title, count, children, defaultOpen = false }: {
  title: string; count?: number; children: React.ReactNode; defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-[#e8e5df] rounded">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-[13px] font-medium text-[#787774] hover:bg-[#f7f6f3] transition-colors"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          {title}
          {count != null && <span className="text-[#9b9a97]">{count}</span>}
        </div>
      </button>
      {open && <div className="px-4 pb-3 border-t border-[#e8e5df]">{children}</div>}
    </div>
  )
}

function ReviewSummaryCard({ approvalInfo }: { approvalInfo: { verdict: string | null; reviewSummary: string | null } }) {
  return (
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
  )
}

function ResultCard({ task, defaultExpanded }: { task: any; defaultExpanded: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const content = typeof (task.result_json ?? task.result) === "string"
    ? (task.result_json ?? task.result)
    : JSON.stringify(task.result_json ?? task.result, null, 2)

  return (
    <Card className="bg-white border border-[#e8e5df] rounded">
      <CardHeader className="cursor-pointer select-none" onClick={() => setExpanded(e => !e)}>
        <div className="flex items-center justify-between">
          <CardTitle className="text-[14px] font-semibold text-[#37352f]">Result</CardTitle>
          {expanded ? <ChevronUp className="h-4 w-4 text-[#9b9a97]" /> : <ChevronDown className="h-4 w-4 text-[#9b9a97]" />}
        </div>
      </CardHeader>
      {expanded && (
        <CardContent>
          <div className="prose max-w-none overflow-auto max-h-[600px]">
            <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
          </div>
        </CardContent>
      )}
    </Card>
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
  const createTask = useCreateTask()

  const [approveOpen, setApproveOpen] = useState(false)
  const [approveNote, setApproveNote] = useState("")
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectNote, setRejectNote] = useState("")
  const [reviseOpen, setReviseOpen] = useState(false)
  const [reviseNote, setReviseNote] = useState("")

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
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate({ to: "/tasks" })}
          className="text-[#9b9a97] hover:text-[#37352f] hover:bg-[#f7f6f3]"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-[20px] font-semibold text-[#37352f]">{task.title}</h1>
            <StatusBadge status={task.effective_status ?? task.status} />
            <TaskTypeBadge type={task.type} />
          </div>
          <div className="flex items-center gap-2 mt-0.5 text-[12px] text-[#9b9a97]">
            <span>{task.workspace}</span>
            {task.cost_usd > 0 && (
              <>
                <span>·</span>
                <span className="font-mono">${Number(task.cost_usd).toFixed(4)}</span>
              </>
            )}
            <span>·</span>
            <span className="font-mono">{task.id}</span>
          </div>
        </div>

        {/* Action buttons in header row */}
        {(canApprove || canReject || canRevise || task.status === "failed") && (
          <div className="flex gap-2 shrink-0">
            {task.status === "failed" && (
              <>
                <Button
                  size="sm"
                  onClick={async () => {
                    await createTask.mutateAsync({
                      workspace: task.workspace,
                      type: task.type,
                      title: task.title,
                      instruction: task.instruction,
                      priority: task.priority,
                      approval_level: task.approval_level,
                    })
                    await api.tasks.dismiss(id)
                    navigate({ to: "/tasks" })
                  }}
                  disabled={createTask.isPending}
                  className="h-[28px] text-[13px] rounded bg-[#2383e2] hover:bg-[#1a73cc] text-white px-3"
                >
                  {createTask.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <RefreshCw className="h-3 w-3 mr-1" />}
                  Retry
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setRejectOpen(true)}
                  className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3] px-3"
                >
                  Dismiss
                </Button>
              </>
            )}
            {task.status === "pending" && (
              <>
                <Button
                  size="sm"
                  onClick={() => setApproveOpen(true)}
                  className="h-[28px] text-[13px] rounded bg-[#2383e2] hover:bg-[#1a73cc] text-white px-3"
                >
                  <Play className="h-3 w-3 mr-1" />
                  Start
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setRejectOpen(true)}
                  className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3] px-3"
                >
                  Cancel
                </Button>
              </>
            )}
            {task.status === "paused" && (
              <>
                <Button
                  size="sm"
                  onClick={() => setApproveOpen(true)}
                  className="h-[28px] text-[13px] rounded bg-[#2383e2] hover:bg-[#1a73cc] text-white px-3"
                >
                  <Check className="h-3 w-3 mr-1" />
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setReviseOpen(true)}
                  className="h-[28px] text-[13px] text-[#787774] hover:bg-[#f7f6f3] px-3"
                >
                  Revise
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setRejectOpen(true)}
                  className="h-[28px] text-[13px] text-[#eb5757] hover:bg-[#eb5757]/5 px-3"
                >
                  Reject
                </Button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Two-column layout: Main content + Sidebar */}
      <div className="flex flex-col lg:flex-row gap-5">
        {/* ── Main column ── */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Status-specific primary content */}
          {task.status === "running" && (
            <AgentLogPanel taskId={id} taskStatus="running" />
          )}

          {task.status === "failed" && task.error && (
            <Card className="bg-[#eb5757]/5 border border-[#eb5757]/20 rounded">
              <CardContent className="py-4">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-[#eb5757] mt-0.5 shrink-0" />
                  <div>
                    <p className="text-[14px] font-medium text-[#eb5757] mb-1">Task Failed</p>
                    <p className="text-[14px] text-[#787774]">{task.error}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {task.status === "failed" && (
            <AgentLogPanel taskId={id} taskStatus="failed" />
          )}

          {task.status === "paused" && approvalInfo.reviewSummary && (
            <ReviewSummaryCard approvalInfo={approvalInfo} />
          )}

          {/* Result */}
          {(task.result_json != null || task.result != null) && (
            <ResultCard task={task} defaultExpanded={true} />
          )}

          {task.status === "pending" && (
            <>
              <p className="text-[14px] text-[#9b9a97]">
                Waiting to start. Click <strong className="text-[#37352f]">Start</strong> to let the agent begin.
              </p>
              {task.instruction && (
                <Card className="bg-white border border-[#e8e5df] rounded">
                  <CardHeader>
                    <CardTitle className="text-[14px] font-semibold text-[#37352f]">Instruction</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="prose max-w-none">
                      <Markdown remarkPlugins={[remarkGfm]}>{task.instruction}</Markdown>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}

          {/* Instruction (if not shown as primary) */}
          {task.status !== "pending" && task.instruction && (
            <CollapsibleSection title="Instruction">
              <div className="prose max-w-none pt-2">
                <Markdown remarkPlugins={[remarkGfm]}>{task.instruction}</Markdown>
              </div>
            </CollapsibleSection>
          )}

          {/* Agent Log (if not already shown as primary) */}
          {task.status !== "running" && task.status !== "failed" && (
            <CollapsibleSection title="Agent Log">
              <div className="pt-2">
                <AgentLogPanel taskId={id} taskStatus={task.status} embedded />
              </div>
            </CollapsibleSection>
          )}
        </div>

        {/* ── Sidebar ── */}
        <div className="lg:w-[320px] shrink-0 space-y-4">
          {/* Properties — always visible */}
          <div className="border border-[#e8e5df] rounded p-4">
            <h3 className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97] mb-3">Properties</h3>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3">
              <Field label="Status" value={task.effective_status ?? task.status} />
              <Field label="Priority" value={task.priority} />
              <Field label="Type" value={getTaskTypeLabel(task.type)} />
              <Field label="Approval" value={task.approval_level === 0 ? "Auto" : task.approval_level === 1 ? "Notify" : "Required"} />
              <Field label="Cost" value={task.cost_usd != null ? `$${Number(task.cost_usd).toFixed(4)}` : undefined} />
              <Field label="Attempt" value={task.max_retries ? `${(task.attempt ?? 0) + 1}/${task.max_retries}` : undefined} />
              {task.depends_on && task.depends_on.length > 0 && (
                <div className="col-span-2">
                  <span className="text-[12px] text-[#9b9a97]">Depends On</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {task.depends_on.map((depId: string) => (
                      <a
                        key={depId}
                        href={`/tasks/${depId}`}
                        className="inline-flex items-center text-[12px] bg-[#f7f6f3] text-[#2383e2] border border-[#e8e5df] rounded px-1.5 py-0.5 hover:bg-[#ebebea] transition-colors"
                      >
                        {depId}
                      </a>
                    ))}
                  </div>
                </div>
              )}
              <Field label="Created" value={task.created_at ? new Date(task.created_at).toLocaleString() : undefined} />
              <Field label="Updated" value={task.updated_at ? new Date(task.updated_at).toLocaleString() : undefined} />
              {task.claimed_by && <Field label="Claimed By" value={task.claimed_by} mono />}
              {task.created_by && <Field label="Created By" value={task.created_by} mono />}
            </div>
          </div>

          {/* Children */}
          {children.length > 0 && (
            <div className="border border-[#e8e5df] rounded p-4">
              <h3 className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97] mb-3">
                Children <span className="text-[#9b9a97]">{children.length}</span>
              </h3>
              <div className="space-y-2">
                {children.map((child: any) => {
                  const review = child.type === "review" ? parseReviewVerdict(child.result_json) : null
                  return (
                    <div
                      key={child.id}
                      className="flex items-start gap-2.5 px-2.5 py-2 rounded bg-[#f7f6f3] hover:bg-[#ebebea] cursor-pointer transition-colors"
                      onClick={() => navigate({ to: "/tasks/$id", params: { id: child.id } })}
                    >
                      <StatusBadge status={child.status} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[13px] text-[#37352f] truncate">{child.title}</span>
                          <TaskTypeBadge type={child.type} />
                        </div>
                        {review?.verdict && (
                          <div className="flex items-center gap-1 mt-0.5">
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
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Activity */}
          <CollapsibleSection title="Activity" defaultOpen={true}>
            <div className="pt-2">
              <ActivityTimeline taskId={id} />
            </div>
          </CollapsibleSection>
        </div>
      </div>

      {/* Approve/Start dialog */}
      <Dialog open={approveOpen} onOpenChange={setApproveOpen}>
        <DialogContent className="bg-white border-[#e8e5df]">
          <DialogHeader>
            <DialogTitle className="text-[16px] font-semibold text-[#37352f]">
              {task.status === "pending" ? "Start Task" : "Approve Task"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            {task.status === "pending" && (
              <p className="text-[13px] text-[#787774]">
                The agent will begin working on this task once you confirm.
              </p>
            )}
            <div className="space-y-1">
              <Label className="text-[12px] text-[#9b9a97]">
                {task.status === "pending" ? "Instructions for the agent (optional)" : "Note (optional)"}
              </Label>
              <Textarea
                value={approveNote}
                onChange={(e) => setApproveNote(e.target.value)}
                className="bg-white border-[#e8e5df] text-[#37352f]"
                placeholder={task.status === "pending" ? "Any specific instructions..." : "Approval note..."}
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
                className={task.status === "pending" ? "bg-[#2383e2] hover:bg-[#1a73cc] text-white" : "bg-[#4dab9a] hover:bg-[#3d9b8b] text-white"}
              >
                {approve.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                {task.status === "pending" ? "Start" : "Approve"}
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
                className="bg-[#eb5757] hover:bg-[#eb5757]/50 text-white"
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
                className="bg-[#2383e2] hover:bg-[#1a73cc] text-white"
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
