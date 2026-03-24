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
import { cn } from "@/lib/utils"

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
        </CardContent>
      </Card>

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
      {task.result != null && (
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
                {typeof task.result === "string"
                  ? task.result
                  : JSON.stringify(task.result, null, 2)}
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
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-gray-800 hover:bg-transparent">
                  <TableHead className="text-gray-400 text-xs">Status</TableHead>
                  <TableHead className="text-gray-400 text-xs">ID</TableHead>
                  <TableHead className="text-gray-400 text-xs">Title</TableHead>
                  <TableHead className="text-gray-400 text-xs">Type</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {children.map((child: any) => (
                  <TableRow
                    key={child.id}
                    className="border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                    onClick={() =>
                      navigate({ to: "/tasks/$id", params: { id: child.id } })
                    }
                  >
                    <TableCell>
                      <StatusBadge status={child.status} />
                    </TableCell>
                    <TableCell className="font-mono text-xs text-gray-400">
                      {String(child.id).slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-gray-50 text-sm">{child.title}</TableCell>
                    <TableCell className="text-gray-400 text-sm">{child.type}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
