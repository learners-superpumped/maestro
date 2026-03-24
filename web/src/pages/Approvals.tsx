import { useNavigate } from "@tanstack/react-router"
import { useApprovals } from "@/hooks/queries/use-approvals"
import { useApproveTask, useRejectTask } from "@/hooks/queries/use-tasks"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { Check, X, Loader2 } from "lucide-react"

export function Approvals() {
  const navigate = useNavigate()
  const { data, isLoading } = useApprovals()
  const approve = useApproveTask()
  const reject = useRejectTask()

  const approvals: any[] = data?.approvals ?? []

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-gray-50">Pending Approvals</h1>
        <p className="text-sm text-gray-400 mt-1">
          {approvals.length} pending
        </p>
      </div>

      <div className="rounded-lg border border-gray-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-800 hover:bg-transparent">
              <TableHead className="text-gray-400 text-xs">Status</TableHead>
              <TableHead className="text-gray-400 text-xs">Task ID</TableHead>
              <TableHead className="text-gray-400 text-xs">Title</TableHead>
              <TableHead className="text-gray-400 text-xs">Workspace</TableHead>
              <TableHead className="text-gray-400 text-xs">Type</TableHead>
              <TableHead className="text-gray-400 text-xs">Draft Preview</TableHead>
              <TableHead className="text-gray-400 text-xs w-28">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <TableRow key={i} className="border-gray-800">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 bg-gray-800" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : approvals.map((item: any) => (
                  <TableRow
                    key={item.task_id || item.id}
                    className="border-gray-800 hover:bg-gray-800/30"
                  >
                    <TableCell>
                      <StatusBadge status={item.status ?? "pending"} />
                    </TableCell>
                    <TableCell
                      className="font-mono text-xs text-indigo-400 cursor-pointer hover:underline"
                      onClick={() => navigate({ to: "/tasks/$id", params: { id: String(item.task_id) } })}
                    >
                      {String(item.task_id).slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-gray-50 text-sm max-w-xs truncate">
                      {item.title ?? "—"}
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm">
                      {item.workspace ?? "—"}
                    </TableCell>
                    <TableCell className="text-gray-400 text-xs font-mono">
                      {item.type ?? "—"}
                    </TableCell>
                    <TableCell className="text-gray-400 text-xs font-mono max-w-xs truncate">
                      {item.draft ? JSON.stringify(item.draft).slice(0, 80) : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation()
                            approve.mutate({ id: String(item.task_id) })
                          }}
                          disabled={approve.isPending}
                          className="h-7 w-7 text-gray-500 hover:text-green-400"
                          title="Approve"
                        >
                          {approve.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation()
                            reject.mutate({ id: String(item.task_id) })
                          }}
                          disabled={reject.isPending}
                          className="h-7 w-7 text-gray-500 hover:text-red-400"
                          title="Reject"
                        >
                          {reject.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && approvals.length === 0 && (
              <TableRow className="border-gray-800">
                <TableCell colSpan={7} className="text-center text-gray-500 py-8">
                  No pending approvals
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
