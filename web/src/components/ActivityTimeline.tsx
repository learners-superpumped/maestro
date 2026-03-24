import { useTaskEvents } from "@/hooks/queries/use-tasks"
import { ActivityEvent } from "@/components/ActivityEvent"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function ActivityTimeline({ taskId }: { taskId: string }) {
  const { data, isLoading, isError } = useTaskEvents(taskId)
  const events: any[] = data?.events ?? []

  if (isError) {
    return (
      <Card className="bg-gray-900 border-gray-800">
        <CardContent className="py-4">
          <p className="text-sm text-gray-500">Could not load activity</p>
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return (
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader><CardTitle className="text-sm text-gray-400">Activity</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-20 bg-gray-800" /></CardContent>
      </Card>
    )
  }

  if (events.length === 0) {
    return (
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader><CardTitle className="text-sm text-gray-400">Activity</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">No activity recorded</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardHeader>
        <CardTitle className="text-sm text-gray-400">Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {events.map((event: any) => (
          <ActivityEvent key={event.id} event={event} />
        ))}
      </CardContent>
    </Card>
  )
}
