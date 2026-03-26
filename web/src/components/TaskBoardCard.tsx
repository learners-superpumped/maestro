import { useNavigate } from "@tanstack/react-router"
import { CornerDownRight, ListChecks, DollarSign, Eye, Sparkles } from "lucide-react"

interface TaskCardProps {
  task: {
    id: string
    task_number: number
    title: string
    type: string
    status: string
    effective_status?: string
    cost_usd?: number
    children_summary?: { total: number; completed: number }
    depends_on_tasks?: { id: string; title: string; status: string }[] | null
  }
}

/** Intermediate statuses shown as a small label in the properties row */
const SUB_STATUS_LABEL: Record<string, string> = {
  approved: "Approved",
  claimed: "Claimed",
  retry_queued: "Retry",
  cancelled: "Cancelled",
}

/** Type config — only system types get an icon */
const TYPE_CONFIG: Record<string, { label: string; icon: typeof Eye }> = {
  review:   { label: "Review",       icon: Eye },
  planning: { label: "Auto-planned", icon: Sparkles },
}

export function TaskBoardCard({ task }: TaskCardProps) {
  const navigate = useNavigate()
  const rawStatus = task.effective_status ?? task.status
  const subLabel = SUB_STATUS_LABEL[rawStatus]
  const typeConfig = TYPE_CONFIG[task.type]
  const deps = task.depends_on_tasks
  const hasDeps = deps && deps.length > 0
  const hasProgress = task.children_summary && task.children_summary.total > 0
  const hasCost = task.cost_usd != null && task.cost_usd > 0

  // Collect all property items for the bottom row
  const hasProperties = typeConfig || subLabel || hasDeps || hasProgress || hasCost

  return (
    <div
      onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
      className="bg-white border border-[#ebebea] rounded px-3 py-2 cursor-pointer hover:bg-[#f9f9f8] transition-colors"
    >
      {/* Title */}
      <div className="flex items-start gap-1.5">
        <span className="text-[11px] text-[#9b9a97] font-mono shrink-0 mt-px">
          MAE-{task.task_number}
        </span>
        <p className="text-[13px] text-[#37352f] leading-[1.4] line-clamp-2">{task.title}</p>
      </div>

      {/* Properties row — Linear style: small icon chips */}
      {hasProperties && (
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          {/* Left group: metadata */}
          <div className="flex items-center gap-1.5 flex-wrap flex-1 min-w-0">
            {typeConfig && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-[#787774]">
                <typeConfig.icon className="h-3 w-3" />
                {typeConfig.label}
              </span>
            )}
            {subLabel && (
              <span className="text-[11px] text-[#787774]">{subLabel}</span>
            )}
            {hasDeps && (
              <span
                className="inline-flex items-center gap-0.5 text-[11px] text-[#787774]"
                title={deps!.map(d => d.title).join(", ")}
              >
                <CornerDownRight className="h-3 w-3" />
                {deps!.length}
              </span>
            )}
            {hasProgress && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-[#787774]">
                <ListChecks className="h-3 w-3" />
                {task.children_summary!.completed}/{task.children_summary!.total}
              </span>
            )}
          </div>
          {/* Right: cost — always pinned right */}
          {hasCost && (
            <span className="inline-flex items-center gap-0.5 text-[11px] text-[#787774] font-mono tabular-nums shrink-0">
              <DollarSign className="h-3 w-3" />
              {Number(task.cost_usd).toFixed(4)}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
