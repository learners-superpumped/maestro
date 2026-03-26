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
        <h1 className="text-[20px] font-semibold text-[#37352f]">Pending Approvals</h1>
        <p className="text-[14px] text-[#9b9a97] mt-1">
          {approvals.length} pending
        </p>
      </div>

      <div className="rounded border border-[#e8e5df] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#e8e5df] hover:bg-transparent">
              <TableHead className="text-[#9b9a97] text-[12px]">Status</TableHead>
              <TableHead className="text-[#9b9a97] text-[12px]">Task ID</TableHead>
              <TableHead className="text-[#9b9a97] text-[12px]">Title</TableHead>
              <TableHead className="text-[#9b9a97] text-[12px]">Type</TableHead>
              <TableHead className="text-[#9b9a97] text-[12px]">Draft Preview</TableHead>
              <TableHead className="text-[#9b9a97] text-[12px] w-28">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <TableRow key={i} className="border-[#e8e5df]">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 bg-[#f7f6f3]" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : approvals.map((item: any) => (
                  <TableRow
                    key={item.task_id || item.id}
                    className="border-[#e8e5df] hover:bg-[#f7f6f3]"
                  >
                    <TableCell>
                      <StatusBadge status={item.status ?? "pending"} />
                    </TableCell>
                    <TableCell
                      className="font-mono text-[12px] text-[#2383e2] cursor-pointer hover:underline"
                      onClick={() => navigate({ to: "/tasks/$id", params: { id: String(item.task_id) } })}
                    >
                      {String(item.task_id).slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-[#37352f] text-[14px] max-w-xs truncate">
                      {item.title ?? "—"}
                    </TableCell>
                    <TableCell className="text-[#9b9a97] text-[12px] font-mono">
                      {item.type ?? "—"}
                    </TableCell>
                    <TableCell className="text-[#9b9a97] text-[12px] font-mono max-w-xs truncate">
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
                          className="h-7 w-7 text-[#9b9a97] hover:text-[#4dab9a] hover:bg-[#f7f6f3]"
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
                          className="h-7 w-7 text-[#9b9a97] hover:text-[#eb5757] hover:bg-[#eb5757]/5"
                          title="Reject"
                        >
                          {reject.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
            {!isLoading && approvals.length === 0 && (
              <TableRow className="border-[#e8e5df]">
                <TableCell colSpan={6} className="text-center text-[#9b9a97] py-8 text-[14px]">
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
