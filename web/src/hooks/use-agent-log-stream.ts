import { useState, useEffect, useRef, useCallback } from "react"

interface LogEntry {
  log_id: number
  log_type: string
  tool_name?: string
  summary: string
  has_content: boolean
  created_at: string
}

export function useAgentLogStream(taskId: string, isLive: boolean) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!isLive || !taskId) return

    setLogs([])
    const protocol = location.protocol === "https:" ? "wss:" : "ws:"
    const ws = new WebSocket(`${protocol}//${location.host}/ws`)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === "task.agent_log" && msg.payload?.task_id === taskId) {
          const entry: LogEntry = {
            log_id: msg.payload.log_id,
            log_type: msg.payload.log_type,
            tool_name: msg.payload.tool_name,
            summary: msg.payload.summary,
            has_content: msg.payload.has_content ?? false,
            created_at: msg.payload.created_at,
          }
          setLogs((prev) => [...prev, entry])
        }
      } catch {}
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [taskId, isLive])

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      })
    }
  }, [])

  return { logs, scrollRef, scrollToBottom }
}
