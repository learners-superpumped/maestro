import { useState } from "react"
import {
  Circle, Check, X, PenLine, User, Play, Pause,
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
}

const EVENT_CONFIG: Record<string, { icon: any; color: string; label: string }> = {
  created: { icon: Circle, color: "text-[#9b9a97]", label: "Created" },
  approved: { icon: Check, color: "text-[#4dab9a]", label: "Approved" },
  rejected: { icon: X, color: "text-[#eb5757]", label: "Rejected" },
  revised: { icon: PenLine, color: "text-[#cb912f]", label: "Revision requested" },
  claimed: { icon: User, color: "text-[#2383e2]", label: "Claimed" },
  running: { icon: Play, color: "text-[#2383e2]", label: "Running" },
  paused: { icon: Pause, color: "text-[#cb912f]", label: "Paused — awaiting approval" },
  completed: { icon: CheckCircle2, color: "text-[#4dab9a]", label: "Completed" },
  failed: { icon: AlertTriangle, color: "text-[#eb5757]", label: "Failed" },
  review_submitted: { icon: Eye, color: "text-[#2383e2]", label: "Review submitted" },
  revision_submitted: { icon: FileEdit, color: "text-[#2383e2]", label: "Revision submitted" },
}

function formatActor(actor: string): string {
  if (actor === "human") return "Human"
  if (actor === "scheduler") return "Scheduler"
  if (actor === "planner") return "Planner"
  if (actor === "system") return "System"
  if (actor.startsWith("agent:")) return `Agent ${actor.slice(6, 12)}`
  return actor
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

export function ActivityEvent({ event }: EventProps) {
  const [expanded, setExpanded] = useState(false)
  const config = EVENT_CONFIG[event.event_type] || EVENT_CONFIG.created
  const Icon = config.icon
  const detail = event.detail_json

  const hasDetail = detail && (detail.note || detail.error || detail.verdict || detail.summary || detail.cost_usd)

  return (
    <div className="flex gap-3 py-2">
      <div className="flex flex-col items-center">
        <div className={cn("h-6 w-6 rounded-full flex items-center justify-center shrink-0", config.color)}>
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="w-px flex-1 bg-[#e8e5df]" />
      </div>
      <div className="flex-1 min-w-0 pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[14px] text-[#37352f]">{config.label}</span>
            <span className="text-[12px] text-[#9b9a97]">by {formatActor(event.actor)}</span>
            {hasDetail && (
              <button onClick={() => setExpanded(!expanded)} className="text-[#9b9a97] hover:text-[#37352f]">
                {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </button>
            )}
          </div>
          <span className="text-[12px] text-[#9b9a97] shrink-0">{formatTime(event.created_at)}</span>
        </div>
        {expanded && detail && (
          <div className="mt-1 text-[12px] text-[#787774] bg-[#f7f6f3] rounded px-3 py-2 space-y-1">
            {detail.note && <p>{detail.note}</p>}
            {detail.error && <p className="text-[#eb5757]">{detail.error}</p>}
            {detail.verdict && <p>Verdict: {detail.verdict}</p>}
            {detail.summary && <p>{detail.summary}</p>}
            {detail.cost_usd && <p>Cost: ${Number(detail.cost_usd).toFixed(4)}</p>}
          </div>
        )}
      </div>
    </div>
  )
}
