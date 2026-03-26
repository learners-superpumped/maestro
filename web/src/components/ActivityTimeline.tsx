import { useTaskEvents } from "@/hooks/queries/use-tasks"
import { ActivityEvent } from "@/components/ActivityEvent"
import { Skeleton } from "@/components/ui/skeleton"

/** Internal events that add noise — hide them */
const HIDDEN_EVENTS = new Set(["claimed"])

/** System auto-approve is noise when followed by claimed/running */
function shouldHide(event: any, _allEvents: any[]): boolean {
  if (HIDDEN_EVENTS.has(event.event_type)) return true

  // Hide "approved" by system (auto-approve) — user approvals are "human" actor
  if (event.event_type === "approved" && event.actor === "system") return true

  return false
}

export function ActivityTimeline({ taskId }: { taskId: string }) {
  const { data, isLoading, isError } = useTaskEvents(taskId)
  const allEvents: any[] = data?.events ?? []

  if (isError) {
    return <p className="text-[13px] text-[#9b9a97] py-2">Could not load activity</p>
  }

  if (isLoading) {
    return <Skeleton className="h-16 bg-[#f7f6f3]" />
  }

  const events = allEvents.filter((e) => !shouldHide(e, allEvents))

  if (events.length === 0) {
    return <p className="text-[13px] text-[#9b9a97] py-2">No activity recorded</p>
  }

  return (
    <div>
      {events.map((event: any, i: number) => (
        <ActivityEvent key={event.id} event={event} isLast={i === events.length - 1} />
      ))}
    </div>
  )
}
