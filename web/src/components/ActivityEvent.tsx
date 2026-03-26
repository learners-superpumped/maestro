import { useState } from "react"
import {
  Circle, Check, X, PenLine, User, Play, Pause,
  CheckCircle2, AlertTriangle, Eye, FileEdit, ChevronDown, ChevronRight
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatRelativeTime } from "@/lib/time"

interface EventProps {
  event: {
    id: string
    task_id: string
    event_type: string
    actor: string
    detail_json?: any
    created_at: string
  }
  isLast?: boolean
}

const EVENT_CONFIG: Record<string, { icon: any; color: string; bg: string; label: string }> = {
  created:            { icon: Circle,        color: "text-[#9b9a97]", bg: "bg-[#f7f6f3]",       label: "Created" },
  approved:           { icon: Check,         color: "text-[#4dab9a]", bg: "bg-[#4dab9a]/10",    label: "Approved" },
  rejected:           { icon: X,             color: "text-[#eb5757]", bg: "bg-[#eb5757]/10",    label: "Rejected" },
  revised:            { icon: PenLine,       color: "text-[#cb912f]", bg: "bg-[#cb912f]/10",    label: "Revision requested" },
  claimed:            { icon: User,          color: "text-[#2383e2]", bg: "bg-[#2383e2]/10",    label: "Claimed" },
  running:            { icon: Play,          color: "text-[#2383e2]", bg: "bg-[#2383e2]/10",    label: "Running" },
  paused:             { icon: Pause,         color: "text-[#cb912f]", bg: "bg-[#cb912f]/10",    label: "Paused" },
  completed:          { icon: CheckCircle2,  color: "text-[#4dab9a]", bg: "bg-[#4dab9a]/10",    label: "Completed" },
  failed:             { icon: AlertTriangle, color: "text-[#eb5757]", bg: "bg-[#eb5757]/10",    label: "Failed" },
  review_submitted:   { icon: Eye,           color: "text-[#2383e2]", bg: "bg-[#2383e2]/10",    label: "Review" },
  revision_submitted: { icon: FileEdit,      color: "text-[#2383e2]", bg: "bg-[#2383e2]/10",    label: "Revision submitted" },
}

function formatActor(actor: string): string {
  if (actor === "human") return "Human"
  if (actor === "scheduler") return "Scheduler"
  if (actor === "planner") return "Planner"
  if (actor === "system") return "System"
  if (actor.startsWith("agent:")) return `Agent ${actor.slice(6, 12)}`
  return actor
}

function getReviewConfig(verdict?: string) {
  if (verdict === "pass") {
    return { icon: CheckCircle2, color: "text-[#4dab9a]", bg: "bg-[#4dab9a]/10" }
  }
  if (verdict === "revise") {
    return { icon: AlertTriangle, color: "text-[#eb5757]", bg: "bg-[#eb5757]/10" }
  }
  return null
}

export function ActivityEvent({ event, isLast = false }: EventProps) {
  const [expanded, setExpanded] = useState(false)
  const detail = event.detail_json
  const baseConfig = EVENT_CONFIG[event.event_type] || EVENT_CONFIG.created

  // Override icon/color for review_submitted based on verdict
  const reviewOverride = event.event_type === "review_submitted" && detail
    ? getReviewConfig(detail.verdict)
    : null
  const config = reviewOverride
    ? { ...baseConfig, ...reviewOverride }
    : baseConfig

  const Icon = config.icon

  const isReview = event.event_type === "review_submitted"
  const isRevision = event.event_type === "revision_submitted"
  const isCompleted = event.event_type === "completed"

  // For non-review/revision events, keep toggle behavior for detail
  const hasToggleDetail = !isReview && detail && (
    detail.note || detail.error || detail.verdict || detail.summary ||
    (detail.cost_usd && !isCompleted)
  )

  // Review label: "Review #N"
  const label = isReview && detail?.review_round
    ? `Review #${detail.review_round}`
    : config.label

  return (
    <div className="flex gap-2.5">
      {/* Timeline track */}
      <div className="flex flex-col items-center">
        <div className={cn("h-5 w-5 rounded-full flex items-center justify-center shrink-0", config.bg, config.color)}>
          <Icon className="h-3 w-3" />
        </div>
        {!isLast && <div className="w-px flex-1 bg-[#e8e5df] my-0.5" />}
      </div>

      {/* Content */}
      <div className={cn("flex-1 min-w-0", isLast ? "pb-0" : "pb-3")}>
        <div className="flex items-baseline justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-[13px] text-[#37352f] font-medium shrink-0">{label}</span>
            {/* Verdict badge for review_submitted */}
            {isReview && detail?.verdict && (
              <span className={cn(
                "text-[11px] font-medium px-1.5 py-0.5 rounded-full leading-none",
                detail.verdict === "pass"
                  ? "text-[#4dab9a] bg-[#4dab9a]/10"
                  : "text-[#eb5757] bg-[#eb5757]/10"
              )}>
                {detail.verdict}
              </span>
            )}
            {hasToggleDetail && (
              <button onClick={() => setExpanded(!expanded)} className="text-[#9b9a97] hover:text-[#787774] shrink-0">
                {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </button>
            )}
          </div>
          <span className="text-[12px] text-[#9b9a97] shrink-0">{formatRelativeTime(event.created_at)}</span>
        </div>

        {/* Actor line */}
        <p className="text-[12px] text-[#9b9a97] mt-0.5">
          {formatActor(event.actor)}
          {/* Inline cost for revision_submitted */}
          {isRevision && detail?.cost_usd && (
            <span className="ml-1.5 text-[#9b9a97]">&middot; ${Number(detail.cost_usd).toFixed(4)}</span>
          )}
          {/* Inline cost for completed */}
          {isCompleted && detail?.cost_usd && (
            <span className="ml-1.5 text-[#9b9a97]">&middot; ${Number(detail.cost_usd).toFixed(4)}</span>
          )}
        </p>

        {/* Review content: always visible, not behind toggle */}
        {isReview && detail && (
          <div className="mt-1.5 space-y-1.5">
            {detail.issues && detail.issues.length > 0 && (
              <div className="text-[12px] bg-[#f7f6f3] rounded px-2.5 py-2">
                <p className="font-medium text-[#37352f] mb-1">Issues ({detail.issues.length})</p>
                <ul className="list-disc list-inside text-[#787774] space-y-0.5">
                  {detail.issues.map((issue: string, i: number) => (
                    <li key={i}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}
            {detail.summary && (
              <p className="text-[12px] text-[#787774] bg-[#f7f6f3] rounded px-2.5 py-2">{detail.summary}</p>
            )}
          </div>
        )}

        {/* Toggle detail for other events */}
        {expanded && detail && !isReview && (
          <div className="mt-1.5 text-[12px] text-[#787774] bg-[#f7f6f3] rounded px-2.5 py-2 space-y-1">
            {detail.note && <p>{detail.note}</p>}
            {detail.error && <p className="text-[#eb5757]">{detail.error}</p>}
            {detail.verdict && <p>Verdict: {detail.verdict}</p>}
            {detail.summary && <p>{detail.summary}</p>}
            {detail.cost_usd && !isCompleted && <p>Cost: ${Number(detail.cost_usd).toFixed(4)}</p>}
          </div>
        )}
      </div>
    </div>
  )
}
