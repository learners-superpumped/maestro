import { useState, useEffect, useRef, useCallback } from "react"

export interface StreamBlock {
  type: "text" | "tool_use" | "tool_result"
  text?: string
  tool_name?: string
  tool_input?: Record<string, unknown>
  tool_use_id?: string
  result?: string
  is_error?: boolean
}

export function useConductorStream(conversationId: string | null) {
  const [streamingBlocks, setStreamingBlocks] = useState<StreamBlock[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const reset = useCallback(() => {
    setStreamingBlocks([])
    setIsStreaming(false)
  }, [])

  useEffect(() => {
    if (!conversationId) return

    const protocol = location.protocol === "https:" ? "wss:" : "ws:"
    const ws = new WebSocket(`${protocol}//${location.host}/ws`)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type !== "conductor.stream") return
        const p = msg.payload
        if (p.conversation_id !== conversationId) return

        if (p.event === "start") {
          setIsStreaming(true)
          setStreamingBlocks([])
        } else if (p.event === "text_delta") {
          setStreamingBlocks((prev) => {
            const last = prev[prev.length - 1]
            if (last && last.type === "text") {
              const updated = [...prev]
              updated[updated.length - 1] = { ...last, text: (last.text || "") + p.text }
              return updated
            }
            return [...prev, { type: "text", text: p.text }]
          })
        } else if (p.event === "tool_use_start") {
          setStreamingBlocks((prev) => [
            ...prev,
            {
              type: "tool_use",
              tool_name: p.tool_name,
              tool_input: p.tool_input,
              tool_use_id: p.tool_use_id,
            },
          ])
        } else if (p.event === "tool_result") {
          setStreamingBlocks((prev) => [
            ...prev,
            {
              type: "tool_result",
              tool_use_id: p.tool_use_id,
              result: p.result,
              is_error: p.is_error,
            },
          ])
        } else if (p.event === "end") {
          setIsStreaming(false)
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      setIsStreaming(false)
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [conversationId])

  return { streamingBlocks, isStreaming, reset }
}
