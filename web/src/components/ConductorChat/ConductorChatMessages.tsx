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
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-4">
      {messages.length === 0 && !isStreaming && (
        <div className="flex flex-col items-center justify-center h-full text-center px-6">
          <div className="text-[32px] mb-3">🎼</div>
          <h3 className="text-[15px] font-medium text-[#37352f] mb-1">Conductor</h3>
          <p className="text-[13px] text-[#9b9a97] leading-relaxed">
            자연어로 지시하면 시스템이 즉시 반응합니다.
            <br />
            Goal/Task 생성, 현황 브리핑, 전략적 의사결정 등을 지시하세요.
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
        <ConductorChatBubble
          role="assistant"
          blocks={streamingBlocks}
        />
      )}

      {isStreaming && streamingBlocks.length === 0 && (
        <div className="flex justify-start mb-3">
          <div className="rounded-2xl rounded-bl-sm px-3.5 py-2.5 bg-[#f7f6f3]">
            <Loader2 className="h-4 w-4 animate-spin text-[#9b9a97]" />
          </div>
        </div>
      )}
    </div>
  )
}
