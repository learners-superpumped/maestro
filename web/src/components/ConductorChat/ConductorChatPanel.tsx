import { useState, useCallback } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { X, Plus, ArrowLeft, MessageSquare } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/api/client"
import { useConductorStream } from "@/hooks/use-conductor-stream"
import { ConductorChatMessages, type ChatMessage } from "./ConductorChatMessages"
import { ConductorChatInput } from "./ConductorChatInput"

interface Conversation {
  id: string
  title?: string
  created_at: string
  updated_at?: string
}

function ConversationList({
  onSelect,
  onNew,
}: {
  onSelect: (id: string) => void
  onNew: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["conductor-conversations"],
    queryFn: () => api.conductor.conversations(),
    refetchInterval: 10_000,
  })

  const conversations: Conversation[] = data?.conversations || []

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#e8e5df]">
        <span className="text-[13px] font-medium text-[#37352f]">Conversations</span>
        <button
          onClick={onNew}
          className="h-6 w-6 flex items-center justify-center rounded hover:bg-[#ebebea] text-[#9b9a97] hover:text-[#37352f] transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="px-3 py-6 text-[13px] text-[#9b9a97] text-center">Loading...</div>
        )}
        {!isLoading && conversations.length === 0 && (
          <div className="px-3 py-6 text-[13px] text-[#9b9a97] text-center">
            No conversations yet
          </div>
        )}
        {conversations.map((conv) => (
          <button
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className="w-full text-left px-3 py-2.5 hover:bg-[#f7f6f3] transition-colors border-b border-[#e8e5df]/50"
          >
            <div className="text-[13px] text-[#37352f] truncate">
              {conv.title || "New conversation"}
            </div>
            <div className="text-[11px] text-[#9b9a97] mt-0.5">
              {new Date(conv.created_at).toLocaleString()}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

export function ConductorChatPanel({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [view, setView] = useState<"list" | "chat">("list")
  const queryClient = useQueryClient()
  const { streamingBlocks, isStreaming, reset } = useConductorStream(conversationId)

  const { data: conversationData } = useQuery({
    queryKey: ["conductor-conversation", conversationId],
    queryFn: () => api.conductor.conversation(conversationId!),
    enabled: !!conversationId,
    refetchInterval: isStreaming ? false : 5_000,
  })

  const messages: ChatMessage[] = (conversationData?.messages || []).map(
    (m: { id: string; role: string; content: string; blocks?: any[]; created_at?: string }) => ({
      id: m.id,
      role: m.role as "user" | "assistant",
      content: m.content || "",
      blocks: m.blocks,
      created_at: m.created_at,
    })
  )

  const handleSelectConversation = useCallback((id: string) => {
    setConversationId(id)
    setView("chat")
    reset()
  }, [reset])

  const handleNewConversation = useCallback(async () => {
    try {
      const result = await api.conductor.createConversation()
      setConversationId(result.id || result.conversation_id)
      setView("chat")
      reset()
      queryClient.invalidateQueries({ queryKey: ["conductor-conversations"] })
    } catch {
      // If creation fails, just switch to chat view with no ID (will create on first message)
      setConversationId(null)
      setView("chat")
    }
  }, [reset, queryClient])

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
        // Refetch conversation to get the user message in the list
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

  const handleBack = useCallback(() => {
    setView("list")
    setConversationId(null)
    reset()
  }, [reset])

  return (
    <div
      className={cn(
        "fixed top-0 right-0 h-full bg-white border-l border-[#e8e5df] shadow-lg z-50",
        "flex flex-col transition-transform duration-200 ease-out",
        "w-[400px]",
        open ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 h-11 px-3 border-b border-[#e8e5df] shrink-0">
        {view === "chat" && (
          <button
            onClick={handleBack}
            className="h-6 w-6 flex items-center justify-center rounded hover:bg-[#ebebea] text-[#9b9a97] hover:text-[#37352f] transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
          </button>
        )}
        <MessageSquare className="h-4 w-4 text-[#9b9a97]" />
        <span className="text-[14px] font-medium text-[#37352f] flex-1">Conductor</span>
        <button
          onClick={onClose}
          className="h-6 w-6 flex items-center justify-center rounded hover:bg-[#ebebea] text-[#9b9a97] hover:text-[#37352f] transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Content */}
      {view === "list" ? (
        <ConversationList
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
        />
      ) : (
        <>
          <ConductorChatMessages
            messages={messages}
            streamingBlocks={streamingBlocks}
            isStreaming={isStreaming}
          />
          <ConductorChatInput onSend={handleSend} disabled={isStreaming} />
        </>
      )}
    </div>
  )
}
