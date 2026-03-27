import { useState, useCallback, useRef, useEffect } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { X, Plus, History, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/api/client"
import { useConductorStream } from "@/hooks/use-conductor-stream"
import { ConductorChatMessages, type ChatMessage } from "./ConductorChatMessages"
import { ConductorChatInput } from "./ConductorChatInput"

interface Conversation {
  id: string
  title?: string
  message_count?: number
  created_at: string
  updated_at?: string
}

function HistoryDropdown({
  conversations,
  currentId,
  onSelect,
  onClose,
}: {
  conversations: Conversation[]
  currentId: string | null
  onSelect: (id: string) => void
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="absolute top-full left-0 right-0 mt-0.5 bg-white border border-[#e8e5df] rounded shadow-md z-50 max-h-[320px] overflow-y-auto"
    >
      {conversations.length === 0 && (
        <div className="px-3 py-4 text-[13px] text-[#9b9a97] text-center">
          대화 이력이 없습니다
        </div>
      )}
      {conversations.map((conv) => (
        <button
          key={conv.id}
          onClick={() => {
            onSelect(conv.id)
            onClose()
          }}
          className={cn(
            "w-full text-left px-3 py-2 text-[13px] hover:bg-[#f7f6f3] transition-colors flex items-center justify-between gap-2",
            conv.id === currentId && "bg-[#f7f6f3]"
          )}
        >
          <span className="text-[#37352f] truncate flex-1">
            {conv.title || "새 대화"}
          </span>
          <span className="text-[11px] text-[#9b9a97] shrink-0">
            {formatRelativeTime(conv.updated_at || conv.created_at)}
          </span>
        </button>
      ))}
    </div>
  )
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "방금"
  if (mins < 60) return `${mins}분 전`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}시간 전`
  const days = Math.floor(hours / 24)
  return `${days}일 전`
}

export function ConductorChatPanel({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const queryClient = useQueryClient()
  const { streamingBlocks, isStreaming, reset } = useConductorStream(conversationId)

  const { data: conversationsData } = useQuery({
    queryKey: ["conductor-conversations"],
    queryFn: () => api.conductor.conversations(),
    refetchInterval: 15_000,
    enabled: open,
  })

  const conversations: Conversation[] = conversationsData?.conversations || []

  const { data: conversationData } = useQuery({
    queryKey: ["conductor-conversation", conversationId],
    queryFn: () => api.conductor.conversation(conversationId!),
    enabled: !!conversationId,
    refetchInterval: isStreaming ? false : 5_000,
  })

  const messages: ChatMessage[] = (conversationData?.messages || []).map(
    (m: { id: string; role: string; content: string; blocks?: unknown[]; created_at?: string }) => ({
      id: m.id,
      role: m.role as "user" | "assistant",
      content: m.content || "",
      blocks: m.blocks,
      created_at: m.created_at,
    })
  )

  const currentTitle = conversationData?.conversation?.title || "Conductor"

  const handleSelectConversation = useCallback(
    (id: string) => {
      setConversationId(id)
      reset()
    },
    [reset]
  )

  const handleNewConversation = useCallback(() => {
    setConversationId(null)
    setHistoryOpen(false)
    reset()
  }, [reset])

  const handleSend = useCallback(
    async (message: string) => {
      try {
        reset()
        const result = await api.conductor.sendMessage({
          conversation_id: conversationId || undefined,
          message,
        })
        if (!conversationId && result.conversation_id) {
          setConversationId(result.conversation_id)
        }
        queryClient.invalidateQueries({
          queryKey: ["conductor-conversation", conversationId || result.conversation_id],
        })
        queryClient.invalidateQueries({ queryKey: ["conductor-conversations"] })
      } catch (err) {
        console.error("Failed to send message:", err)
      }
    },
    [conversationId, reset, queryClient]
  )

  return (
    <div
      className={cn(
        "fixed top-0 right-0 h-full bg-white border-l border-[#e8e5df] z-50",
        "flex flex-col transition-transform duration-200 ease-out",
        "w-[400px]",
        open ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Header */}
      <div className="relative flex items-center gap-1.5 h-11 px-3 border-b border-[#e8e5df] shrink-0">
        <button
          onClick={() => setHistoryOpen(!historyOpen)}
          className="flex items-center gap-1 h-6 px-1.5 rounded hover:bg-[#ebebea] text-[#9b9a97] hover:text-[#37352f] transition-colors"
          title="대화 이력"
        >
          <History className="h-3.5 w-3.5" />
          <ChevronDown className="h-3 w-3" />
        </button>
        <span className="text-[14px] font-medium text-[#37352f] flex-1 truncate">
          {conversationId ? currentTitle : "Conductor"}
        </span>
        <button
          onClick={handleNewConversation}
          className="h-6 w-6 flex items-center justify-center rounded hover:bg-[#ebebea] text-[#9b9a97] hover:text-[#37352f] transition-colors"
          title="새 대화"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onClose}
          className="h-6 w-6 flex items-center justify-center rounded hover:bg-[#ebebea] text-[#9b9a97] hover:text-[#37352f] transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>

        {/* History Dropdown */}
        {historyOpen && (
          <HistoryDropdown
            conversations={conversations}
            currentId={conversationId}
            onSelect={handleSelectConversation}
            onClose={() => setHistoryOpen(false)}
          />
        )}
      </div>

      {/* Messages — always visible, ready to chat */}
      <ConductorChatMessages
        messages={messages}
        streamingBlocks={streamingBlocks}
        isStreaming={isStreaming}
      />
      <ConductorChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  )
}
