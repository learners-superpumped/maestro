import { useNavigate } from "@tanstack/react-router"
import { AlertTriangle, Check, X } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { useApproveTask, useRejectTask } from "@/hooks/queries/use-tasks"

interface Approval {
  task_id: string
  title: string
  status: string
  type?: string
}

interface Props {
  approvals: Approval[]
  loading: boolean
}

export function ApprovalsWidget({ approvals, loading }: Props) {
  const navigate = useNavigate()
  const approve = useApproveTask()
  const reject = useRejectTask()

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <AlertTriangle className="h-3.5 w-3.5 text-[#cb912f]" />
        <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
          Pending Approvals
        </span>
        {!loading && approvals.length > 0 && (
          <span
            className="ml-auto text-[10px] px-1.5 py-0.5 rounded font-semibold"
            style={{ color: "#cb912f", backgroundColor: "#fff3e0" }}
          >
            {approvals.length}
          </span>
        )}
      </div>

      <div className="space-y-px">
        {loading &&
          [1, 2].map((i) => (
            <div key={i} className="flex items-center gap-2 px-1 py-1.5">
              <Skeleton className="h-3.5 flex-1 bg-[#f7f6f3]" />
              <Skeleton className="h-7 w-7 rounded bg-[#f7f6f3]" />
              <Skeleton className="h-7 w-7 rounded bg-[#f7f6f3]" />
            </div>
          ))}

        {!loading && approvals.length === 0 && (
          <div className="px-1 py-2 text-[12px] text-[#9b9a97]">승인 대기 없음</div>
        )}

        {!loading &&
          approvals.map((appr) => (
            <div
              key={appr.task_id}
              className="flex items-center gap-1 px-1 py-1.5 rounded hover:bg-[#f9f9f8] transition-colors"
            >
              <button
                onClick={() => navigate({ to: "/tasks/$id", params: { id: appr.task_id } })}
                className="flex-1 min-w-0 text-left"
              >
                <span className="text-[12px] text-[#37352f] truncate block">{appr.title}</span>
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  approve.mutate({ id: appr.task_id })
                }}
                className="h-7 w-7 flex items-center justify-center rounded text-[#9b9a97] hover:text-[#4dab9a] hover:bg-[#f7f6f3] transition-colors shrink-0"
                title="Approve"
              >
                <Check className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  reject.mutate({ id: appr.task_id })
                }}
                className="h-7 w-7 flex items-center justify-center rounded text-[#9b9a97] hover:text-[#eb5757] transition-colors shrink-0"
                title="Reject"
                style={{ "--tw-bg-opacity": "0.03" } as React.CSSProperties}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
      </div>
    </div>
  )
}
