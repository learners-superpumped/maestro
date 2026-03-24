import { useEffect } from "react"
import { useTaskLogs } from "@/hooks/queries/use-tasks"
import { useAgentLogStream } from "@/hooks/use-agent-log-stream"
import { AgentLogEntry } from "@/components/AgentLogEntry"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface AgentLogPanelProps {
  taskId: string
  taskStatus: string
}

export function AgentLogPanel({ taskId, taskStatus }: AgentLogPanelProps) {
  const isLive = taskStatus === "running"

  // Historical mode: fetch from API
  const { data, isLoading, isError } = useTaskLogs(isLive ? "" : taskId)
  const historicalLogs: any[] = data?.logs ?? []

  // Live mode: stream from WebSocket
  const { logs: liveLogs, scrollRef, scrollToBottom } = useAgentLogStream(taskId, isLive)

  // Auto-scroll when new live entries arrive
  useEffect(() => {
    if (isLive && liveLogs.length > 0) {
      // Small delay to let DOM render the new entry
      const timer = setTimeout(scrollToBottom, 50)
      return () => clearTimeout(timer)
    }
  }, [isLive, liveLogs.length, scrollToBottom])

  const logs = isLive
    ? liveLogs.map((l, i) => ({
        id: l.log_id || i,
        log_type: l.log_type,
        tool_name: l.tool_name,
        summary: l.summary,
        has_content: l.has_content,
        created_at: l.created_at,
      }))
    : historicalLogs

  if (isError && !isLive) {
    return (
      <Card className="bg-white border border-[#e8e5df] rounded">
        <CardContent className="py-4">
          <p className="text-[14px] text-[#9b9a97]">Could not load agent logs</p>
        </CardContent>
      </Card>
    )
  }

  if (!isLive && isLoading) {
    return (
      <Card className="bg-white border border-[#e8e5df] rounded">
        <CardHeader>
          <CardTitle className="text-[14px] font-semibold text-[#37352f]">Agent Log</CardTitle>
        </CardHeader>
        <CardContent><Skeleton className="h-20 bg-[#f7f6f3]" /></CardContent>
      </Card>
    )
  }

  if (logs.length === 0 && !isLive) return null

  return (
    <Card className="bg-white border border-[#e8e5df] rounded">
      <CardHeader className="pb-2">
        <CardTitle className="text-[14px] font-semibold text-[#37352f] flex items-center gap-2">
          {isLive && (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#4dab9a] opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-[#4dab9a]" />
            </span>
          )}
          Agent Log
          {isLive && <span className="text-[12px] font-normal text-[#9b9a97]">Live</span>}
          {!isLive && logs.length > 0 && (
            <span className="text-[12px] font-normal text-[#9b9a97]">{logs.length} entries</span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          ref={scrollRef}
          className="max-h-[400px] overflow-y-auto"
        >
          {logs.map((log: any, index: number) => (
            <div
              key={log.id ?? index}
              className="animate-in fade-in duration-300"
              style={{ animationDelay: isLive ? "0ms" : `${index * 20}ms` }}
            >
              <AgentLogEntry taskId={taskId} log={log} />
            </div>
          ))}
          {isLive && logs.length === 0 && (
            <div className="flex items-center gap-2 py-4 text-[14px] text-[#9b9a97]">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#4dab9a] opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[#4dab9a]" />
              </span>
              Waiting for agent activity...
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
