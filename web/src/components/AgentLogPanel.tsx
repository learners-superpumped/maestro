import { useTaskLogs } from "@/hooks/queries/use-tasks"
import { AgentLogEntry } from "@/components/AgentLogEntry"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface AgentLogPanelProps {
  taskId: string
  taskStatus: string
}

export function AgentLogPanel({ taskId, taskStatus }: AgentLogPanelProps) {
  const { data, isLoading, isError } = useTaskLogs(taskId)
  const logs: any[] = data?.logs ?? []

  const isLive = taskStatus === "running"

  if (isError) {
    return (
      <Card className="bg-gray-900 border-gray-800">
        <CardContent className="py-4">
          <p className="text-sm text-gray-500">Could not load agent logs</p>
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return (
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader><CardTitle className="text-sm text-gray-400">Agent Log</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-20 bg-gray-800" /></CardContent>
      </Card>
    )
  }

  if (logs.length === 0) return null

  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardHeader>
        <CardTitle className="text-sm text-gray-400 flex items-center gap-2">
          {isLive && <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />}
          {isLive ? "Agent Log — Live" : "Agent Log"}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="max-h-96 overflow-y-auto space-y-0">
          {logs.map((log: any) => (
            <AgentLogEntry key={log.id} taskId={taskId} log={log} />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
