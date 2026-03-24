import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

type WsStatus = "connected" | "disconnected" | "connecting"

export function useWebSocket() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<WsStatus>("disconnected")

  useEffect(() => {
    let ws: WebSocket
    let reconnectDelay = 1000
    let closed = false

    function connect() {
      if (closed) return
      setStatus("connecting")
      const protocol = location.protocol === "https:" ? "wss:" : "ws:"
      ws = new WebSocket(`${protocol}//${location.host}/ws`)

      ws.onopen = () => {
        setStatus("connected")
        reconnectDelay = 1000
      }
      ws.onmessage = (e) => {
        try {
          const { type } = JSON.parse(e.data as string) as { type: string }
          if (type.startsWith("task.")) {
            queryClient.invalidateQueries({ queryKey: ["tasks"] })
            queryClient.invalidateQueries({ queryKey: ["root-tasks"] })
            queryClient.invalidateQueries({ queryKey: ["task-events"] })
          }
          if (type.startsWith("approval."))
            queryClient.invalidateQueries({ queryKey: ["approvals"] })
          if (type.startsWith("asset."))
            queryClient.invalidateQueries({ queryKey: ["assets"] })
          if (type.startsWith("schedule."))
            queryClient.invalidateQueries({ queryKey: ["schedules"] })
          if (type.startsWith("rule."))
            queryClient.invalidateQueries({ queryKey: ["rules"] })
          if (type.startsWith("workspace."))
            queryClient.invalidateQueries({ queryKey: ["workspaces"] })
          if (
            type.startsWith("task.") ||
            type.startsWith("asset.") ||
            type.startsWith("approval.")
          ) {
            queryClient.invalidateQueries({ queryKey: ["stats"] })
          }
        } catch {
          // ignore parse errors
        }
      }
      ws.onclose = () => {
        setStatus("disconnected")
        if (!closed) {
          setTimeout(connect, reconnectDelay)
          reconnectDelay = Math.min(reconnectDelay * 2, 30000)
        }
      }
    }

    connect()
    return () => {
      closed = true
      ws?.close()
    }
  }, [queryClient])

  return status
}
