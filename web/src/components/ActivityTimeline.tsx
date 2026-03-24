import { useTaskEvents } from "@/hooks/queries/use-tasks"
import { ActivityEvent } from "@/components/ActivityEvent"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function ActivityTimeline({ taskId }: { taskId: string }) {
  const { data, isLoading, isError } = useTaskEvents(taskId)
  const events: any[] = data?.events ?? []

  if (isError) {
    return (
      <Card className="bg-white border border-[#e8e5df] rounded">
        <CardContent className="py-4">
          <p className="text-[14px] text-[#9b9a97]">Could not load activity</p>
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return (
      <Card className="bg-white border border-[#e8e5df] rounded">
        <CardHeader><CardTitle className="text-[14px] font-semibold text-[#37352f]">Activity</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-20 bg-[#f7f6f3]" /></CardContent>
      </Card>
    )
  }

  if (events.length === 0) {
    return (
      <Card className="bg-white border border-[#e8e5df] rounded">
        <CardHeader><CardTitle className="text-[14px] font-semibold text-[#37352f]">Activity</CardTitle></CardHeader>
        <CardContent>
          <p className="text-[14px] text-[#9b9a97]">No activity recorded</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="bg-white border border-[#e8e5df] rounded">
      <CardHeader>
        <CardTitle className="text-[14px] font-semibold text-[#37352f]">Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {events.map((event: any) => (
          <ActivityEvent key={event.id} event={event} />
        ))}
      </CardContent>
    </Card>
  )
}
