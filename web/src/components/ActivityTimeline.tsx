import { useState } from "react"
import { useTaskEvents } from "@/hooks/queries/use-tasks"
import { ActivityEvent } from "@/components/ActivityEvent"
import { Skeleton } from "@/components/ui/skeleton"

const COLLAPSED_COUNT = 5

export function ActivityTimeline({ taskId }: { taskId: string }) {
  const { data, isLoading, isError } = useTaskEvents(taskId)
  const events: any[] = data?.events ?? []
  const [expanded, setExpanded] = useState(false)

  if (isError) {
    return <p className="text-[13px] text-[#9b9a97] py-2">Could not load activity</p>
  }

  if (isLoading) {
    return <Skeleton className="h-16 bg-[#f7f6f3]" />
  }

  if (events.length === 0) {
    return <p className="text-[13px] text-[#9b9a97] py-2">No activity recorded</p>
  }

  const hasMore = events.length > COLLAPSED_COUNT
  const visible = expanded ? events : events.slice(0, COLLAPSED_COUNT)

  return (
    <div>
      {visible.map((event: any, i: number) => (
        <ActivityEvent key={event.id} event={event} isLast={i === visible.length - 1} />
      ))}
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[12px] text-[#2383e2] hover:text-[#1a73cc] mt-1.5 transition-colors"
        >
          {expanded ? "Show less" : `Show ${events.length - COLLAPSED_COUNT} more`}
        </button>
      )}
    </div>
  )
}
