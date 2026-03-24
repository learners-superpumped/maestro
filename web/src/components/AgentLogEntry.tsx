import { useState } from "react"
import { useLogContent } from "@/hooks/queries/use-tasks"
import { LogContentView } from "@/components/LogContentView"
import {
  MessageSquare, FileText, Pencil, FilePlus, Terminal, Search, Wrench,
  ChevronRight, ChevronDown, Loader2
} from "lucide-react"
import { cn } from "@/lib/utils"

interface LogEntryProps {
  taskId: string
  log: {
    id: number
    log_type: string
    tool_name?: string
    summary: string
    has_content?: boolean
    created_at: string
  }
}

const TOOL_ICONS: Record<string, { icon: any; color: string }> = {
  Read: { icon: FileText, color: "text-[#2383e2]" },
  Edit: { icon: Pencil, color: "text-[#cb912f]" },
  Write: { icon: FilePlus, color: "text-[#4dab9a]" },
  Bash: { icon: Terminal, color: "text-[#9065b0]" },
  Grep: { icon: Search, color: "text-[#2383e2]" },
}

export function AgentLogEntry({ taskId, log }: LogEntryProps) {
  const [expanded, setExpanded] = useState(false)
  const { data: fullLog, isLoading } = useLogContent(taskId, expanded ? log.id : null)

  const toolConfig = log.tool_name ? TOOL_ICONS[log.tool_name] : null
  const Icon = log.log_type === "text" ? MessageSquare
    : log.log_type === "tool_result" ? ChevronRight
    : toolConfig?.icon || Wrench
  const iconColor = log.log_type === "text" ? "text-[#9b9a97]"
    : log.log_type === "tool_result" ? "text-[#9b9a97]"
    : toolConfig?.color || "text-[#9b9a97]"

  const time = new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })

  return (
    <div className="py-1.5">
      <div className="flex items-start gap-2">
        <span className="text-[12px] text-[#9b9a97] font-mono shrink-0 w-16 pt-0.5">{time}</span>
        <Icon className={cn("h-3.5 w-3.5 shrink-0 mt-0.5", iconColor)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            {log.log_type === "text" ? (
              <span className="text-[14px] text-[#787774]">{log.summary}</span>
            ) : (
              <span className="text-[14px] text-[#787774]">
                {log.tool_name && <span className="text-[#37352f]">{log.tool_name}</span>}
                {log.tool_name && " → "}
                {log.summary}
              </span>
            )}
            {log.has_content && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-[#9b9a97] hover:text-[#37352f] shrink-0"
              >
                {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </button>
            )}
          </div>
          {expanded && (
            isLoading ? (
              <div className="mt-1 flex items-center gap-1 text-[12px] text-[#9b9a97]">
                <Loader2 className="h-3 w-3 animate-spin" /> Loading...
              </div>
            ) : fullLog?.content ? (
              <LogContentView logType={log.log_type} toolName={log.tool_name} content={fullLog.content} />
            ) : null
          )}
        </div>
      </div>
    </div>
  )
}
