interface LogContentProps {
  logType: string
  toolName?: string
  content: string
}

export function LogContentView({ logType, toolName, content }: LogContentProps) {
  if (!content) return null

  // Edit tool — try to show diff format
  if (logType === "tool_use" && toolName === "Edit") {
    try {
      const parsed = JSON.parse(content)
      return (
        <div className="mt-1 rounded bg-[#f7f6f3] border border-[#e8e5df] p-3 text-[13px] font-mono overflow-auto max-h-64">
          {parsed.old_string && (
            <div className="text-[#eb5757]">- {parsed.old_string}</div>
          )}
          {parsed.new_string && (
            <div className="text-[#4dab9a]">+ {parsed.new_string}</div>
          )}
        </div>
      )
    } catch { /* fall through */ }
  }

  // Bash tool_use — show command
  if (logType === "tool_use" && toolName === "Bash") {
    try {
      const parsed = JSON.parse(content)
      return (
        <div className="mt-1 rounded bg-[#f7f6f3] border border-[#e8e5df] p-3 text-[13px] font-mono overflow-auto max-h-64 text-[#37352f]">
          $ {parsed.command}
        </div>
      )
    } catch { /* fall through */ }
  }

  // tool_result or other — show as code block
  return (
    <div className="mt-1 rounded bg-[#f7f6f3] border border-[#e8e5df] p-3 text-[13px] font-mono overflow-auto max-h-64 text-[#37352f] whitespace-pre-wrap">
      {content.length > 5000 ? content.slice(0, 5000) + "\n... (truncated)" : content}
    </div>
  )
}
