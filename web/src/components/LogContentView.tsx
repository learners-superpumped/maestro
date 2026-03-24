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
        <div className="mt-1 rounded bg-gray-950 border border-gray-800 p-3 text-xs font-mono overflow-auto max-h-64">
          {parsed.old_string && (
            <div className="text-red-400">- {parsed.old_string}</div>
          )}
          {parsed.new_string && (
            <div className="text-green-400">+ {parsed.new_string}</div>
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
        <div className="mt-1 rounded bg-gray-950 border border-gray-800 p-3 text-xs font-mono overflow-auto max-h-64 text-gray-300">
          $ {parsed.command}
        </div>
      )
    } catch { /* fall through */ }
  }

  // tool_result or other — show as code block
  return (
    <div className="mt-1 rounded bg-gray-950 border border-gray-800 p-3 text-xs font-mono overflow-auto max-h-64 text-gray-300 whitespace-pre-wrap">
      {content.length > 5000 ? content.slice(0, 5000) + "\n... (truncated)" : content}
    </div>
  )
}
