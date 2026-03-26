import { TaskBoardCard } from "@/components/TaskBoardCard"
import { Circle, Loader2, Pause, CheckCircle2, XCircle } from "lucide-react"

const COLUMN_ORDER = ["pending", "running", "paused", "completed", "failed"]

const COLUMN_CONFIG: Record<string, { label: string; icon: any; iconClass: string }> = {
  pending:   { label: "Pending",   icon: Circle,       iconClass: "text-[#9b9a97]" },
  running:   { label: "Running",   icon: Loader2,      iconClass: "text-[#f2994a] animate-spin" },
  paused:    { label: "Paused",    icon: Pause,        iconClass: "text-[#9b9a97]" },
  completed: { label: "Completed", icon: CheckCircle2, iconClass: "text-[#4dab9a]" },
  failed:    { label: "Failed",    icon: XCircle,      iconClass: "text-[#eb5757]" },
}

/**
 * Maps internal statuses to board columns.
 * approved/claimed/retry_queued are intermediate states
 * that belong in visible columns.
 */
const STATUS_TO_COLUMN: Record<string, string> = {
  pending: "pending",
  approved: "running",
  claimed: "running",
  running: "running",
  paused: "paused",
  retry_queued: "running",
  completed: "completed",
  failed: "failed",
  cancelled: "failed",
}

interface TaskBoardProps {
  tasks: any[]
}

export function TaskBoard({ tasks }: TaskBoardProps) {
  const grouped: Record<string, any[]> = {}
  for (const col of COLUMN_ORDER) grouped[col] = []
  for (const task of tasks) {
    const raw = task.effective_status ?? task.status
    const col = STATUS_TO_COLUMN[raw] ?? raw
    if (grouped[col]) grouped[col].push(task)
  }

  return (
    <div className="flex gap-2 overflow-x-auto pb-4">
      {COLUMN_ORDER.map((status) => {
        const config = COLUMN_CONFIG[status]
        const count = grouped[status].length
        const Icon = config.icon
        return (
          <div key={status} className="flex-shrink-0 w-[280px]">
            {/* Column header — Linear style: icon + label + count */}
            <div className="flex items-center gap-1.5 mb-1 px-2 py-1.5">
              <Icon className={`h-3.5 w-3.5 shrink-0 ${config.iconClass}`} />
              <span className="text-[13px] font-medium text-[#37352f]">
                {config.label}
              </span>
              <span className="text-[13px] text-[#b4b4b0]">
                {count}
              </span>
            </div>
            {/* Cards */}
            <div className="flex flex-col gap-px">
              {grouped[status].map((task: any) => (
                <TaskBoardCard key={task.id} task={task} />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
