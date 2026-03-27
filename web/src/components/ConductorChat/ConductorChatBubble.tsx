import { useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { ChevronRight, ChevronDown, Wrench, CheckCircle2, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { StreamBlock } from "@/hooks/use-conductor-stream"

interface ToolCard {
  type: "tool_use" | "tool_result"
  tool_name?: string
  tool_input?: Record<string, unknown>
  tool_use_id?: string
  result?: string
  is_error?: boolean
}

function ToolUseCard({ block, resultBlock }: { block: ToolCard; resultBlock?: ToolCard }) {
  const [expanded, setExpanded] = useState(false)

  const inputSummary = block.tool_input
    ? Object.entries(block.tool_input)
        .slice(0, 3)
        .map(([k, v]) => {
          const val = typeof v === "string" ? (v.length > 40 ? v.slice(0, 40) + "..." : v) : JSON.stringify(v)
          return `${k}: ${val}`
        })
        .join(", ")
    : ""

  return (
    <div className="mx-4 my-1 rounded border border-[#e8e5df] bg-[#f7f6f3] text-[13px]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 w-full px-2.5 py-1.5 text-left hover:bg-[#ebebea] rounded transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-[#9b9a97] shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 text-[#9b9a97] shrink-0" />
        )}
        <Wrench className="h-3 w-3 text-[#9065b0] shrink-0" />
        <span className="font-medium text-[#37352f]">{block.tool_name}</span>
        {resultBlock && (
          resultBlock.is_error ? (
            <XCircle className="h-3 w-3 text-[#eb5757] shrink-0 ml-auto" />
          ) : (
            <CheckCircle2 className="h-3 w-3 text-[#4dab9a] shrink-0 ml-auto" />
          )
        )}
      </button>
      {expanded && (
        <div className="px-2.5 pb-2 space-y-1.5">
          {inputSummary && (
            <div className="text-[12px] text-[#787774] font-mono bg-white rounded px-2 py-1 border border-[#e8e5df] whitespace-pre-wrap break-all">
              {inputSummary}
            </div>
          )}
          {resultBlock?.result && (
            <div
              className={cn(
                "text-[12px] font-mono rounded px-2 py-1 border whitespace-pre-wrap break-all max-h-40 overflow-auto",
                resultBlock.is_error
                  ? "bg-[#fce8e8] border-[#eb5757]/20 text-[#eb5757]"
                  : "bg-white border-[#e8e5df] text-[#787774]"
              )}
            >
              {resultBlock.result.length > 500
                ? resultBlock.result.slice(0, 500) + "..."
                : resultBlock.result}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface MessageContent {
  role: "user" | "assistant"
  text?: string
  blocks?: StreamBlock[]
}

export function ConductorChatBubble({ role, text, blocks }: MessageContent) {
  if (role === "user") {
    return (
      <div className="px-4 py-2.5 border-b border-[#e8e5df]/50 bg-white">
        <div className="text-[12px] font-medium text-[#9b9a97] mb-1">You</div>
        <div className="text-[14px] text-[#37352f] leading-relaxed whitespace-pre-wrap">
          {text}
        </div>
      </div>
    )
  }

  // Assistant message — flat, no bubble
  const renderedBlocks = blocks || (text ? [{ type: "text" as const, text }] : [])

  // Pair tool_use with their tool_result
  const pairedResults = new Map<string, ToolCard>()
  for (const b of renderedBlocks) {
    if (b.type === "tool_result" && b.tool_use_id) {
      pairedResults.set(b.tool_use_id, b as ToolCard)
    }
  }

  return (
    <div className="border-b border-[#e8e5df]/50 bg-[#fafaf9]">
      <div className="px-4 pt-2.5 pb-1">
        <div className="text-[12px] font-medium text-[#9065b0] mb-1">Conductor</div>
      </div>
      {renderedBlocks.map((block, i) => {
        if (block.type === "text" && block.text) {
          return (
            <div
              key={i}
              className="px-4 pb-2.5 text-[14px] text-[#37352f] leading-relaxed prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-headings:my-2 prose-pre:my-1 prose-code:text-[13px]"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.text}</ReactMarkdown>
            </div>
          )
        }
        if (block.type === "tool_use") {
          return (
            <ToolUseCard
              key={i}
              block={block as ToolCard}
              resultBlock={block.tool_use_id ? pairedResults.get(block.tool_use_id) : undefined}
            />
          )
        }
        return null
      })}
      <div className="h-1" />
    </div>
  )
}
