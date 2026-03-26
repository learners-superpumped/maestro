import { useState } from "react"
import {
  Circle, Check, X, PenLine, Play, Pause,
  CheckCircle2, AlertTriangle, Eye, FileEdit, ChevronDown, ChevronRight
} from "lucide-react"
import { cn } from "@/lib/utils"

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
  running:            { icon: Play,          color: "text-[#2383e2]", bg: "bg-[#2383e2]/10",    label: "Execution started" },
  paused:             { icon: Pause,         color: "text-[#cb912f]", bg: "bg-[#cb912f]/10",    label: "Paused" },
  completed:          { icon: CheckCircle2,  color: "text-[#4dab9a]", bg: "bg-[#4dab9a]/10",    label: "Completed" },
  failed:             { icon: AlertTriangle, color: "text-[#eb5757]", bg: "bg-[#eb5757]/10",    label: "Failed" },
  review_submitted:   { icon: Eye,           color: "text-[#2383e2]", bg: "bg-[#2383e2]/10",    label: "Review" },
  revision_submitted: { icon: FileEdit,      color: "text-[#2383e2]", bg: "bg-[#2383e2]/10",    label: "Revision completed" },
}

function formatEventTime(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHr / 24)

  // Same day → show time "14:05"
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
  }
  // Yesterday
  if (diffDay === 1) return "yesterday"
  // Within a week
  if (diffDay < 7) return `${diffDay}d ago`
  return date.toLocaleDateString([], { month: "short", day: "numeric" })
}

function formatActor(actor: string): string | null {
  if (actor === "system") return null  // hide system actor
  if (actor === "human") return "You"
  if (actor === "scheduler") return "Scheduler"
  if (actor === "planner") return "Planner"
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

  const reviewOverride = event.event_type === "review_submitted" && detail
    ? getReviewConfig(detail.verdict)
    : null
  const config = reviewOverride ? { ...baseConfig, ...reviewOverride } : baseConfig
  const Icon = config.icon

  const isReview = event.event_type === "review_submitted"
  const isRevision = event.event_type === "revision_submitted"
  const isCompleted = event.event_type === "completed"

  const hasToggleDetail = !isReview && detail && (
    detail.note || detail.error || (detail.verdict && !isCompleted) || (detail.summary && !isCompleted)
  )

  const label = isReview && detail?.review_round
    ? `Review #${detail.review_round}`
    : config.label

  const actorText = formatActor(event.actor)
  const costText = (isCompleted || isRevision) && detail?.cost_usd
    ? `$${Number(detail.cost_usd).toFixed(2)}`
    : null

  // Build subtitle parts
  const subtitleParts: string[] = []
  if (actorText) subtitleParts.push(actorText)
  if (costText) subtitleParts.push(costText)

  return (
    <div className="flex gap-2.5">
      {/* Timeline dot */}
      <div className="flex flex-col items-center">
        <div className={cn("h-5 w-5 rounded-full flex items-center justify-center shrink-0", config.bg, config.color)}>
          <Icon className="h-3 w-3" />
        </div>
        {!isLast && <div className="w-px flex-1 bg-[#e8e5df] my-0.5" />}
      </div>

      {/* Content */}
      <div className={cn("flex-1 min-w-0", isLast ? "pb-0" : "pb-3")}>
        {/* Header line */}
        <div className="flex items-baseline justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-[13px] text-[#37352f] font-medium shrink-0">{label}</span>
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
          <span className="text-[11px] text-[#b4b4b0] shrink-0 tabular-nums">{formatEventTime(event.created_at)}</span>
        </div>

        {/* Subtitle: actor · cost */}
        {subtitleParts.length > 0 && (
          <p className="text-[12px] text-[#9b9a97] mt-0.5">
            {subtitleParts.join(" · ")}
          </p>
        )}

        {/* Review inline content */}
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
          </div>
        )}
      </div>
    </div>
  )
}
