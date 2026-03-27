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
          No conversation history
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
            {conv.title || "New conversation"}
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
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function ConductorChatPanel({
  open,
  onClose,
  requestedConversationId,
  onConversationOpened,
}: {
  open: boolean
  onClose: () => void
  requestedConversationId?: string
  onConversationOpened?: () => void
}) {
  const [conversationId, setConversationId] = useState<string | null>(null)

  useEffect(() => {
    if (requestedConversationId && open) {
      setConversationId(requestedConversationId)
      onConversationOpened?.()
    }
  }, [requestedConversationId, open, onConversationOpened])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const queryClient = useQueryClient()
  const { streamingBlocks, isStreaming, reset } = useConductorStream(conversationId)

  // Input is disabled while sending or streaming
  const inputDisabled = sending || isStreaming

  // Clear sending state once streaming starts or assistant response arrives via refetch
  useEffect(() => {
    if (isStreaming && sending) {
      setSending(false)
    }
  }, [isStreaming, sending])

  const { data: conversationsData } = useQuery({
    queryKey: ["conductor-conversations"],
    queryFn: () => api.conductor.conversations(),
    refetchInterval: 15_000,
    enabled: open,
  })

  const conversations: Conversation[] = conversationsData?.conversations || []

  // Refetch immediately when streaming ends (blocks still present = just finished),
  // then fall back to normal 5s polling
  const needsImmediateRefetch = !isStreaming && streamingBlocks.length > 0
  const { data: conversationData } = useQuery({
    queryKey: ["conductor-conversation", conversationId],
    queryFn: () => api.conductor.conversation(conversationId!),
    enabled: !!conversationId,
    refetchInterval: isStreaming ? false : needsImmediateRefetch ? 500 : 5_000,
  })

  const serverMessages: ChatMessage[] = (conversationData?.messages || []).map(
    (m: { id: string; role: string; content: string; blocks?: unknown[]; created_at?: string }) => ({
      id: m.id,
      role: m.role as "user" | "assistant",
      content: m.content || "",
      blocks: m.blocks,
      created_at: m.created_at,
    })
  )

  // Show optimistic user message immediately while waiting for server
  const messages: ChatMessage[] = pendingMessage
    ? [
        ...serverMessages,
        {
          id: "pending",
          role: "user" as const,
          content: pendingMessage,
        },
      ]
    : serverMessages

  // Fallback: if server messages include an assistant reply, sending is done
  useEffect(() => {
    if (sending && serverMessages.length > 0) {
      const lastMsg = serverMessages[serverMessages.length - 1]
      if (lastMsg.role === "assistant") {
        setSending(false)
        setPendingMessage(null)
      }
    }
  }, [sending, serverMessages])

  // Clear pending message once server has it
  useEffect(() => {
    if (pendingMessage && serverMessages.some((m) => m.role === "user" && m.content === pendingMessage)) {
      setPendingMessage(null)
    }
  }, [serverMessages, pendingMessage])

  // Clear streaming blocks once server has the assistant reply (prevents duplicate display)
  useEffect(() => {
    if (!isStreaming && streamingBlocks.length > 0 && serverMessages.length > 0) {
      const lastMsg = serverMessages[serverMessages.length - 1]
      if (lastMsg.role === "assistant") {
        reset()
      }
    }
  }, [isStreaming, streamingBlocks.length, serverMessages, reset])

  const currentTitle = conversationData?.conversation?.title || "Conductor"

  const handleSelectConversation = useCallback(
    (id: string) => {
      setConversationId(id)
      setPendingMessage(null)
      reset()
    },
    [reset]
  )

  const handleNewConversation = useCallback(() => {
    setConversationId(null)
    setHistoryOpen(false)
    setPendingMessage(null)
    setSending(false)
    reset()
  }, [reset])

  const handleSend = useCallback(
    async (message: string) => {
      // Immediately show user message and disable input
      setPendingMessage(message)
      setSending(true)
      reset()

      try {
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
        setSending(false)
        setPendingMessage(null)
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
          title="History"
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
          title="New conversation"
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
        isStreaming={isStreaming || sending}
      />
      <ConductorChatInput onSend={handleSend} disabled={inputDisabled} />
    </div>
  )
}
