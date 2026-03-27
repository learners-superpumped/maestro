import { useNavigate } from "@tanstack/react-router"
import { Calendar, ChevronRight } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"

interface Schedule {
  id: string
  name: string
  enabled: number | boolean
  cron?: string
  interval_ms?: number
  next_run_at?: string
}

function formatNextRun(schedule: Schedule): string {
  if (schedule.next_run_at) {
    const d = new Date(schedule.next_run_at)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    const tomorrow = new Date(now)
    tomorrow.setDate(tomorrow.getDate() + 1)
    const isTomorrow = d.toDateString() === tomorrow.toDateString()
    const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    if (isToday) return `Today at ${time}`
    if (isTomorrow) return `Tomorrow at ${time}`
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + ` at ${time}`
  }
  if (schedule.interval_ms) {
    const mins = Math.round(schedule.interval_ms / 60000)
    if (mins < 60) return `every ${mins}m`
    return `every ${Math.round(mins / 60)}h`
  }
  if (schedule.cron) return schedule.cron
  return "—"
}

interface Props {
  schedules: Schedule[]
  loading: boolean
}

export function SchedulesWidget({ schedules, loading }: Props) {
  const navigate = useNavigate()
  const shown = schedules
    .filter((s) => s.enabled)
    .slice(0, 2)

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
            Upcoming Schedules
          </span>
        </div>
        <button
          onClick={() => navigate({ to: "/schedules" })}
          className="flex items-center gap-0.5 text-[12px] text-[#2383e2] hover:underline"
        >
          View all
          <ChevronRight className="h-3 w-3" />
        </button>
      </div>

      <div className="space-y-px">
        {loading &&
          [1, 2].map((i) => (
            <div key={i} className="flex items-center gap-2 px-1 py-1.5">
              <Skeleton className="h-3.5 w-3.5 rounded bg-[#f7f6f3]" />
              <Skeleton className="h-3.5 flex-1 bg-[#f7f6f3]" />
              <Skeleton className="h-3.5 w-16 bg-[#f7f6f3]" />
            </div>
          ))}

        {!loading && shown.length === 0 && (
          <div className="px-1 py-2 text-[12px] text-[#9b9a97]">예정된 스케줄 없음</div>
        )}

        {!loading &&
          shown.map((sch) => (
            <button
              key={sch.id}
              onClick={() => navigate({ to: "/schedules" })}
              className="w-full flex items-center gap-2 px-1 py-1.5 rounded hover:bg-[#f9f9f8] transition-colors text-left"
            >
              <Calendar className="h-3.5 w-3.5 text-[#9b9a97] shrink-0" />
              <span className="text-[12px] text-[#37352f] truncate flex-1">{sch.name}</span>
              <span className="text-[11px] text-[#9b9a97] shrink-0">{formatNextRun(sch)}</span>
            </button>
          ))}
      </div>
    </div>
  )
}
