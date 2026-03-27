import { useState } from "react"
import { useLogContent } from "@/hooks/queries/use-tasks"
import { LogContentView } from "@/components/LogContentView"
import {
  MessageSquare, FileText, Pencil, FilePlus, Terminal, Search, Wrench,
  ChevronRight, ChevronDown, Loader2, CheckCircle2
} from "lucide-react"
import { cn } from "@/lib/utils"

interface LogData {
  id: number
  log_type: string
  tool_name?: string
  summary: string
  has_content?: boolean
  created_at: string
}

interface LogEntryProps {
  taskId: string
  log: LogData
  /** Paired tool_result for tool_use entries */
  resultLog?: LogData
}

const TOOL_ICONS: Record<string, { icon: any; color: string; border: string }> = {
  Read:  { icon: FileText,  color: "text-[#2383e2]", border: "border-l-[#2383e2]" },
  Edit:  { icon: Pencil,    color: "text-[#cb912f]", border: "border-l-[#cb912f]" },
  Write: { icon: FilePlus,  color: "text-[#4dab9a]", border: "border-l-[#4dab9a]" },
  Bash:  { icon: Terminal,  color: "text-[#9065b0]", border: "border-l-[#9065b0]" },
  Grep:  { icon: Search,    color: "text-[#2383e2]", border: "border-l-[#2383e2]" },
}

function ToolContent({ taskId, log }: { taskId: string; log: LogData }) {
  const { data: fullLog, isLoading } = useLogContent(taskId, log.id)

  if (isLoading) {
    return (
      <div className="mt-1.5 flex items-center gap-1 text-[12px] text-[#9b9a97]">
        <Loader2 className="h-3 w-3 animate-spin" /> Loading...
      </div>
    )
  }
  if (!fullLog?.content) return null
  return <LogContentView logType={log.log_type} toolName={log.tool_name} content={fullLog.content} />
}

export function AgentLogEntry({ taskId, log, resultLog }: LogEntryProps) {
  const [expanded, setExpanded] = useState(false)

  const time = new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })

  // --- Text log ---
  if (log.log_type === "text") {
    return (
      <div className="py-1.5 pl-1">
        <div className="flex items-start gap-2">
          <span className="text-[12px] text-[#9b9a97] font-mono shrink-0 w-16 pt-0.5">{time}</span>
          <MessageSquare className="h-3.5 w-3.5 shrink-0 mt-0.5 text-[#9b9a97]" />
          <span className="text-[14px] text-[#787774] leading-relaxed">{log.summary}</span>
        </div>
      </div>
    )
  }

  // --- Tool result (standalone, not paired) ---
  if (log.log_type === "tool_result" && !resultLog) {
    return (
      <div className="py-1 pl-1">
        <div className="flex items-start gap-2">
          <span className="text-[12px] text-[#9b9a97] font-mono shrink-0 w-16 pt-0.5">{time}</span>
          <ChevronRight className="h-3.5 w-3.5 shrink-0 mt-0.5 text-[#9b9a97]" />
          <span className="text-[13px] text-[#9b9a97] font-mono truncate">{log.summary}</span>
        </div>
      </div>
    )
  }

  // --- Tool use (with optional paired result) ---
  const toolConfig = log.tool_name ? TOOL_ICONS[log.tool_name] : null
  const Icon = toolConfig?.icon || Wrench
  const iconColor = toolConfig?.color || "text-[#9b9a97]"
  const borderColor = toolConfig?.border || "border-l-[#d4d3d0]"
  const canExpand = log.has_content || resultLog?.has_content

  return (
    <div className={cn("my-1 rounded-r bg-[#f7f6f3]/60 border-l-2", borderColor)}>
      <button
        onClick={() => canExpand && setExpanded(!expanded)}
        className={cn(
          "flex items-center gap-2 w-full px-2.5 py-1.5 text-left",
          canExpand && "hover:bg-[#ebebea]/50 transition-colors cursor-pointer",
          !canExpand && "cursor-default"
        )}
      >
        <span className="text-[12px] text-[#9b9a97] font-mono shrink-0 w-16">{time}</span>
        <Icon className={cn("h-3.5 w-3.5 shrink-0", iconColor)} />
        <span className="text-[13px] text-[#37352f] font-medium shrink-0">{log.tool_name}</span>
        <span className="text-[13px] text-[#787774] truncate flex-1 min-w-0">{log.summary}</span>
        {resultLog && (
          <CheckCircle2 className="h-3.5 w-3.5 text-[#4dab9a] shrink-0" />
        )}
        {canExpand && (
          expanded
            ? <ChevronDown className="h-3 w-3 text-[#9b9a97] shrink-0" />
            : <ChevronRight className="h-3 w-3 text-[#9b9a97] shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-2.5 pb-2 space-y-1.5">
          {log.has_content && <ToolContent taskId={taskId} log={log} />}
          {resultLog && resultLog.has_content && (
            <div className="mt-1">
              <div className="text-[11px] font-medium text-[#9b9a97] mb-0.5">Result</div>
              <ToolContent taskId={taskId} log={resultLog} />
            </div>
          )}
          {resultLog && !resultLog.has_content && resultLog.summary && (
            <div className="text-[12px] text-[#9b9a97] font-mono bg-white rounded px-2 py-1 border border-[#e8e5df]">
              {resultLog.summary}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
