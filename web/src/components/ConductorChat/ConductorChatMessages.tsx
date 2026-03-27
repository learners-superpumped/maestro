import { useEffect, useRef } from "react"
import { Loader2 } from "lucide-react"
import { ConductorChatBubble } from "./ConductorChatBubble"
import type { StreamBlock } from "@/hooks/use-conductor-stream"

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  blocks?: StreamBlock[]
  created_at?: string
}

interface ConductorChatMessagesProps {
  messages: ChatMessage[]
  streamingBlocks: StreamBlock[]
  isStreaming: boolean
}

export function ConductorChatMessages({
  messages,
  streamingBlocks,
  isStreaming,
}: ConductorChatMessagesProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      })
    }
  }, [messages, streamingBlocks])

  const hasContent = messages.length > 0 || isStreaming

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto">
      {!hasContent && (
        <div className="flex flex-col items-center justify-end h-full pb-4 px-6">
          <p className="text-[13px] text-[#9b9a97] mb-1">Maestro Conductor</p>
          <p className="text-[12px] text-[#9b9a97]/70">
            Goals · Tasks · Briefings · Decisions
          </p>
        </div>
      )}

      {messages.map((msg) => (
        <ConductorChatBubble
          key={msg.id}
          role={msg.role}
          text={msg.content}
          blocks={msg.blocks}
        />
      ))}

      {streamingBlocks.length > 0 && (
        <ConductorChatBubble role="assistant" blocks={streamingBlocks} />
      )}

      {isStreaming && streamingBlocks.length === 0 && (
        <div className="flex items-center gap-2 px-4 py-3 text-[13px] text-[#9b9a97]">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          <span>Thinking...</span>
        </div>
      )}
    </div>
  )
}
