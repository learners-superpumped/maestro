import { useTaskEvents } from "@/hooks/queries/use-tasks"
import { ActivityEvent } from "@/components/ActivityEvent"
import { Skeleton } from "@/components/ui/skeleton"

export function ActivityTimeline({ taskId }: { taskId: string }) {
  const { data, isLoading, isError } = useTaskEvents(taskId)
  const events: any[] = data?.events ?? []

  if (isError) {
    return <p className="text-[14px] text-[#9b9a97] py-2">Could not load activity</p>
  }

  if (isLoading) {
    return <Skeleton className="h-16 bg-[#f7f6f3]" />
  }

  if (events.length === 0) {
    return <p className="text-[14px] text-[#9b9a97] py-2">No activity recorded</p>
  }

  return (
    <div>
      {events.map((event: any) => (
        <ActivityEvent key={event.id} event={event} />
      ))}
    </div>
  )
}
