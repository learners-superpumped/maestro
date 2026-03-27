import { useEffect, useMemo } from "react"
import { useTaskLogs } from "@/hooks/queries/use-tasks"
import { useAgentLogStream } from "@/hooks/use-agent-log-stream"
import { AgentLogEntry } from "@/components/AgentLogEntry"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface AgentLogPanelProps {
  taskId: string
  taskStatus: string
  /** When true, renders without Card wrapper (for use inside CollapsibleSection) */
  embedded?: boolean
}

export function AgentLogPanel({ taskId, taskStatus, embedded = false }: AgentLogPanelProps) {
  const isLive = taskStatus === "running"

  const { data, isLoading, isError } = useTaskLogs(isLive ? "" : taskId)
  const historicalLogs: any[] = data?.logs ?? []

  const { logs: liveLogs, scrollRef, scrollToBottom } = useAgentLogStream(taskId, isLive)

  useEffect(() => {
    if (isLive && liveLogs.length > 0) {
      const timer = setTimeout(scrollToBottom, 50)
      return () => clearTimeout(timer)
    }
  }, [isLive, liveLogs.length, scrollToBottom])

  const mappedLiveLogs = liveLogs.map((l, i) => ({
    id: l.log_id || i,
    log_type: l.log_type,
    tool_name: l.tool_name,
    summary: l.summary,
    has_content: l.has_content,
    created_at: l.created_at,
  }))

  // Use liveLogs as fallback during the transition from live → historical
  // to prevent the brief flash of empty content while API fetches
  const rawLogs = isLive
    ? mappedLiveLogs
    : (!isLoading || historicalLogs.length > 0)
      ? historicalLogs
      : mappedLiveLogs

  // Pair tool_use with subsequent tool_result entries
  const logs = useMemo(() => {
    const paired: { log: any; resultLog?: any }[] = []
    const skipIndices = new Set<number>()

    for (let i = 0; i < rawLogs.length; i++) {
      if (skipIndices.has(i)) continue
      const entry = rawLogs[i]

      if (entry.log_type === "tool_use" && i + 1 < rawLogs.length) {
        const next = rawLogs[i + 1]
        if (next.log_type === "tool_result") {
          paired.push({ log: entry, resultLog: next })
          skipIndices.add(i + 1)
          continue
        }
      }
      paired.push({ log: entry })
    }
    return paired
  }, [rawLogs])

  // Error/loading/empty for embedded mode (no Card wrapper)
  if (embedded) {
    if (isError && !isLive) return <p className="text-[14px] text-[#9b9a97] py-2">Could not load agent logs</p>
    if (!isLive && isLoading) return <Skeleton className="h-16 bg-[#f7f6f3]" />
    if (logs.length === 0 && !isLive) return <p className="text-[14px] text-[#9b9a97] py-2">No logs recorded</p>

    return (
      <div ref={scrollRef} className="max-h-[400px] overflow-y-auto">
        {logs.map(({ log, resultLog }, index) => (
          <div key={log.id ?? index} className="animate-in" style={{ animationDelay: isLive ? "0ms" : `${index * 20}ms` }}>
            <AgentLogEntry taskId={taskId} log={log} resultLog={resultLog} />
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
    )
  }

  // Standalone mode (with Card wrapper — used as primary content for running/failed)
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
        <div ref={scrollRef} className="max-h-[400px] overflow-y-auto">
          {logs.map(({ log, resultLog }, index) => (
            <div key={log.id ?? index} className="animate-in" style={{ animationDelay: isLive ? "0ms" : `${index * 20}ms` }}>
              <AgentLogEntry taskId={taskId} log={log} resultLog={resultLog} />
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
