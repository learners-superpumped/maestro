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

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto">
      {messages.length === 0 && !isStreaming && (
        <div className="flex flex-col items-center justify-center h-full text-center px-8">
          <p className="text-[14px] font-medium text-[#37352f] mb-1">Conductor</p>
          <p className="text-[13px] text-[#9b9a97] leading-relaxed">
            자연어로 시스템을 지휘하세요
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

      {isStreaming && streamingBlocks.length > 0 && (
        <ConductorChatBubble role="assistant" blocks={streamingBlocks} />
      )}

      {isStreaming && streamingBlocks.length === 0 && (
        <div className="flex items-center gap-2 px-4 py-3 text-[13px] text-[#9b9a97]">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          <span>처리 중...</span>
        </div>
      )}
    </div>
  )
}
